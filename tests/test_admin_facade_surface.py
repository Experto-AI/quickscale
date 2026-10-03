"""Public-surface lock for the backups ``admin`` facade.

``admin`` keeps its public import path and re-exports public names one way
from the private siblings and the service module; the registered admin classes
stay defined here.  This test pins public names only — no private name and no
incidental import — resolves the service seams through the module that defines
each name, and checks that explicit re-exports are the defining objects
(decisions.md, Split-Facade Seams).
"""

from datetime import UTC, datetime
import importlib
from unittest.mock import MagicMock, patch

from django.contrib import admin as django_admin

from quickscale_modules_backups import (
    admin as backups_admin,
    models as backups_models,
    services as backups_services,
)

ADMIN_SURFACE: frozenset[str] = frozenset(
    {
        "BackupArtifact",
        "BackupArtifactAdmin",
        "BackupError",
        "BackupPolicy",
        "BackupPolicyAdmin",
        "BackupPolicyRestoreForm",
        "BackupRestoreBlocked",
        "BackupSnapshot",
        "RestoreSourceResolutionMode",
        "STALE_RESTORE_THRESHOLD_MINUTES",
        "delete_artifact_files",
        "dispatch_background_create",
        "dispatch_background_prune",
        "dispatch_background_restore",
        "download_backup_path",
        "ensure_default_policy",
        "is_restore_stale",
        "prepare_admin_uploaded_restore_artifact",
        "reset_stale_restore",
        "restore_admin_uploaded_backup",
        "restore_backup_artifact",
        "validate_backup_artifact",
    }
)

INCIDENTAL_NAMES = frozenset(
    {
        "Any",
        "FileResponse",
        "HttpRequest",
        "HttpResponse",
        "HttpResponseRedirect",
        "Path",
        "PermissionDenied",
        "TemplateResponse",
        "admin",
        "annotations",
        "cast",
        "format_html",
        "forms",
        "json",
        "messages",
        "path",
        "reverse",
    }
)

REEXPORTED_FROM: dict[str, str] = {
    "BackupArtifact": "quickscale_modules_backups.models",
    "BackupPolicy": "quickscale_modules_backups.models",
    "BackupPolicyRestoreForm": "quickscale_modules_backups._admin_forms",
    "BackupSnapshot": "quickscale_modules_backups.models",
    "delete_artifact_files": "quickscale_modules_backups.services",
    "dispatch_background_create": "quickscale_modules_backups.services",
    "dispatch_background_prune": "quickscale_modules_backups.services",
    "dispatch_background_restore": "quickscale_modules_backups.services",
    "download_backup_path": "quickscale_modules_backups.services",
    "ensure_default_policy": "quickscale_modules_backups.services",
    "is_restore_stale": "quickscale_modules_backups.services",
    "prepare_admin_uploaded_restore_artifact": "quickscale_modules_backups.services",
    "reset_stale_restore": "quickscale_modules_backups.services",
    "restore_admin_uploaded_backup": "quickscale_modules_backups.services",
    "restore_backup_artifact": "quickscale_modules_backups.services",
    "validate_backup_artifact": "quickscale_modules_backups.services",
}


def test_public_surface_importable() -> None:
    """Every pinned public name is present on the facade."""
    missing = sorted(ADMIN_SURFACE - set(dir(backups_admin)))
    assert not missing, f"admin is missing public names: {missing}"


def test_surface_pins_no_private_or_incidental_names() -> None:
    """The expected set names public facade API only."""
    for name in ADMIN_SURFACE:
        assert not name.startswith("_"), f"admin pins private {name!r}"
    incidental = ADMIN_SURFACE & INCIDENTAL_NAMES
    assert not incidental, f"admin pins incidental names: {sorted(incidental)}"


def test_declared_surface_is_public() -> None:
    """``__all__`` stays a subset of the pinned public surface."""
    assert set(backups_admin.__all__) <= set(ADMIN_SURFACE)
    assert backups_admin.__all__ == sorted(backups_admin.__all__)


def test_reexports_are_the_defining_objects() -> None:
    """A re-export is the same object as its defining module's binding."""
    for name, source in REEXPORTED_FROM.items():
        defining = importlib.import_module(source)
        assert getattr(backups_admin, name) is getattr(defining, name), (
            f"admin.{name} is not {source}.{name}"
        )


def test_download_seam_resolves_on_services() -> None:
    """The download service resolves through ``services`` at call time."""
    registered_admin = django_admin.site._registry[backups_models.BackupArtifact]

    ready_artifact = MagicMock()
    ready_artifact.status = backups_models.BackupArtifact.Status.READY
    with patch.object(backups_services, "download_backup_path") as lookup:
        assert registered_admin._has_downloadable_local_file(ready_artifact) is True
    lookup.assert_called_once_with(ready_artifact)

    deleted_artifact = MagicMock()
    deleted_artifact.status = backups_models.BackupArtifact.Status.DELETED
    with patch.object(backups_services, "download_backup_path") as lookup:
        assert registered_admin._has_downloadable_local_file(deleted_artifact) is False
    lookup.assert_not_called()


def test_moved_service_lookups_resolve_on_services() -> None:
    """Former admin-module service lookups resolve on the service module."""
    artifact_admin = django_admin.site._registry[backups_models.BackupArtifact]
    policy_admin = django_admin.site._registry[backups_models.BackupPolicy]

    restoring = MagicMock()
    restoring.status = backups_models.BackupArtifact.Status.RESTORING
    restoring.restore_started_at = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    with patch.object(backups_services, "is_restore_stale", return_value=True) as stale:
        assert "Stale" in artifact_admin.stale_restore_warning(restoring)
        ineligible = policy_admin._get_admin_restore_ineligible_reason(restoring)
        assert ineligible is not None
        assert ineligible.startswith("This backup artifact's restore appears stale")
    assert stale.call_count == 2

    with (
        patch.object(
            backups_services, "validate_backup_artifact", return_value=[]
        ) as validate,
        patch.object(django_admin.ModelAdmin, "message_user"),
    ):
        artifact_admin.validate_selected_backups(MagicMock(), [MagicMock()])
    validate.assert_called_once()

    with (
        patch.object(backups_services, "is_restore_stale", return_value=True),
        patch.object(backups_services, "reset_stale_restore") as reset,
        patch.object(django_admin.ModelAdmin, "message_user"),
    ):
        artifact_admin.reset_stale_restore_action(MagicMock(), [restoring])
    reset.assert_called_once_with(restoring)

    with (
        patch.object(backups_services, "delete_artifact_files") as delete,
        patch.object(django_admin.ModelAdmin, "delete_queryset"),
    ):
        artifact_admin.delete_queryset(MagicMock(), [MagicMock()])
    delete.assert_called_once()
