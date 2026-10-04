"""Artifact admin implementation for the backups admin surface.

``BackupArtifactAdmin`` is defined and registered in
``quickscale_modules_backups.admin``, which subclasses
:class:`BackupArtifactAdminBase` here. The service-call methods resolve their
collaborators through ``quickscale_modules_backups.services`` at call time, so
the service module stays the lookup site for tests.
"""

from __future__ import annotations

import json
from typing import Any, cast

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.urls import path, reverse
from django.utils.html import format_html

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    BackupRestoreBlocked,
)


def _reset_stale_summary(reset_count: int, skip_count: int, error_count: int) -> str:
    """Compose the operator summary for one stale-restore reset action."""
    parts: list[str] = []
    if reset_count:
        parts.append(f"{reset_count} stale restore(s) reset to Failed")
    if skip_count:
        parts.append(f"{skip_count} artifact(s) skipped")
    if error_count:
        parts.append(f"{error_count} artifact(s) errored")
    if not parts:
        return "No stale restore artifacts were selected."
    return ". ".join(parts) + "."


class BackupArtifactAdminBase(admin.ModelAdmin):
    """Admin interface for backup artifact history and download access."""

    list_display = [
        "filename",
        "status",
        "stale_restore_warning",
        "snapshot_status_badge",
        "snapshot_provenance",
        "restore_scope_badge",
        "storage_target",
        "storage_location",
        "checksum_sha256",
        "validated_at",
        "size_bytes",
        "trigger",
        "created_at",
        "initiated_by",
        "download_link",
    ]
    list_filter = ["status", "storage_target", "trigger", "created_at"]
    search_fields = ["filename", "checksum_sha256", "database_name", "remote_key"]
    readonly_fields = [
        "filename",
        "snapshot_reference",
        "snapshot_status_badge",
        "snapshot_source_environment",
        "storage_target",
        "restore_scope_badge",
        "stale_restore_warning",
        "local_path",
        "remote_key",
        "checksum_sha256",
        "size_bytes",
        "backup_format",
        "database_engine",
        "database_name",
        "database_server_major",
        "dump_client_major",
        "metadata_pretty",
        "status",
        "trigger",
        "initiated_by",
        "validation_notes",
        "validated_at",
        "restore_started_at",
        "restore_error",
        "restored_at",
        "deleted_at",
        "created_at",
        "updated_at",
        "download_path_display",
        "download_link",
        "admin_availability_notice",
        "restore_cli_notice",
    ]
    fieldsets = [
        (
            "Artifact",
            {
                "fields": [
                    "filename",
                    "status",
                    "snapshot_status_badge",
                    "snapshot_reference",
                    "snapshot_source_environment",
                    "restore_scope_badge",
                    "storage_target",
                    "backup_format",
                    "trigger",
                    "initiated_by",
                    "created_at",
                    "updated_at",
                ]
            },
        ),
        (
            "Storage",
            {
                "fields": [
                    "local_path",
                    "remote_key",
                    "download_path_display",
                    "download_link",
                    "admin_availability_notice",
                ]
            },
        ),
        (
            "Integrity",
            {
                "fields": [
                    "checksum_sha256",
                    "size_bytes",
                    "database_engine",
                    "database_name",
                    "database_server_major",
                    "dump_client_major",
                    "validation_notes",
                    "validated_at",
                    "restore_started_at",
                    "restore_error",
                    "restored_at",
                    "deleted_at",
                    "metadata_pretty",
                    "restore_cli_notice",
                ]
            },
        ),
    ]
    actions = ["validate_selected_backups", "reset_stale_restore_action"]
    change_list_template = "admin/quickscale_backups/backupartifact/change_list.html"

    def get_queryset(self, request: HttpRequest) -> Any:
        """Load related user and snapshot data for provenance projections."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "initiated_by",
                "authoritative_snapshot",
            )
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Artifacts are created through commands or the policy admin."""
        return False

    def get_urls(self) -> list[Any]:
        """Add a staff-protected download endpoint for local backup files."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops/create/",
                self.admin_site.admin_view(self.create_backup_view),
                name="quickscale_backups_backupartifact_create",
            ),
            path(
                "<int:artifact_id>/download/",
                self.admin_site.admin_view(self.download_view),
                name="quickscale_backups_backupartifact_download",
            ),
        ]
        return custom_urls + urls

    def _get_policy_admin(self) -> Any:
        """Return the registered BackupPolicy admin when available.

        Implemented on the registered subclass, which owns the concrete
        ``BackupPolicyAdmin`` type check.
        """
        raise NotImplementedError

    def _has_policy_change_permission(self, request: HttpRequest) -> bool:
        """Mirror the existing BackupPolicy change gate for backup creation."""
        policy_admin = self._get_policy_admin()
        if policy_admin is None:
            return False
        return bool(policy_admin.has_change_permission(request))

    def _require_policy_change_permission(self, request: HttpRequest) -> None:
        """Require the existing BackupPolicy change permission boundary."""
        if not self._has_policy_change_permission(request):
            raise PermissionDenied

    def _require_view_or_change_permission(self, request: HttpRequest) -> None:
        """Require BackupArtifact view or change permission for admin downloads."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

    def _get_snapshot(self, obj: BackupArtifact) -> BackupSnapshot | None:
        """Return the attached authoritative snapshot when one is tracked."""
        if hasattr(obj, "authoritative_snapshot"):
            return cast(BackupSnapshot | None, obj.authoritative_snapshot)
        return None

    def _snapshot_metadata(self, obj: BackupArtifact) -> dict[str, Any]:
        """Return artifact metadata as a dict for provenance details."""
        metadata = obj.metadata_json
        if isinstance(metadata, dict):
            return metadata
        return {}

    def _snapshot_reference_value(self, obj: BackupArtifact) -> str | None:
        """Return the tracked snapshot identifier when one is available."""
        snapshot = self._get_snapshot(obj)
        if snapshot is not None:
            return cast(str | None, snapshot.snapshot_id)

        snapshot_id = str(self._snapshot_metadata(obj).get("snapshot_id", "")).strip()
        return snapshot_id or None

    def _snapshot_status_value(self, obj: BackupArtifact) -> str | None:
        """Return the tracked snapshot lifecycle status when one is available."""
        snapshot = self._get_snapshot(obj)
        if snapshot is not None:
            return cast(str | None, snapshot.status)

        snapshot_status = str(
            self._snapshot_metadata(obj).get("snapshot_status", "")
        ).strip()
        return snapshot_status or None

    def _snapshot_source_environment_value(self, obj: BackupArtifact) -> str | None:
        """Return the recorded source environment for the attached snapshot."""
        snapshot = self._get_snapshot(obj)
        if snapshot is None:
            return None

        source_environment = snapshot.source_environment.strip()
        return source_environment or None

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Expose a create-backup affordance only to policy mutation operators."""
        merged_context = {
            **(extra_context or {}),
            "show_create_backup_control": self._has_policy_change_permission(request),
        }
        return super().changelist_view(request, merged_context)

    def create_backup_view(self, request: HttpRequest) -> HttpResponseRedirect:
        """Delegate artifact-side backup creation to the existing policy admin flow."""
        self._require_policy_change_permission(request)
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:quickscale_backups_backupartifact_changelist")
            )

        policy_admin = self._get_policy_admin()
        if policy_admin is None:
            raise PermissionDenied

        policy_admin.create_backup_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_backups_backupartifact_changelist")
        )

    def _has_downloadable_local_file(self, obj: BackupArtifact) -> bool:
        """Return whether the admin can still offer a local download action.

        Implemented on the registered subclass, which keeps the
        ``download_backup_path`` lookup on the services module.
        """
        raise NotImplementedError

    def download_view(
        self,
        request: HttpRequest,
        artifact_id: int,
    ) -> FileResponse | HttpResponseRedirect:
        """Stream a local backup file to authenticated staff users.

        Implemented on the registered subclass, which keeps the
        ``download_backup_path`` lookup on the services module.
        """
        raise NotImplementedError

    def _is_restore_stale(self, artifact: BackupArtifact) -> bool:
        """Return whether the artifact's restore is stale.

        Implemented on the registered subclass, which keeps the         service
        lookup on the services module.
        """
        raise NotImplementedError

    def _reset_stale_restore(self, artifact: BackupArtifact) -> None:
        """Reset one stranded restore to ``Status.FAILED``.

        Implemented on the registered subclass, which keeps the         service
        lookup on the services module.
        """
        raise NotImplementedError

    def _validate_backup_artifact(self, artifact: BackupArtifact) -> Any:
        """Validate one artifact and return its issues.

        Implemented on the registered subclass, which keeps the         service
        lookup on the services module.
        """
        raise NotImplementedError

    def _delete_artifact_files(self, artifact: BackupArtifact) -> None:
        """Delete one artifact's local and remote files.

        Implemented on the registered subclass, which keeps the         service
        lookup on the services module.
        """
        raise NotImplementedError

    def _reset_stale_artifacts(self, queryset: Any) -> tuple[int, int, int]:
        """Reset each stale restore in *queryset*, counting outcomes."""
        reset_count = 0
        skip_count = 0
        error_count = 0
        for artifact in queryset:
            if artifact.status != BackupArtifact.Status.RESTORING:
                skip_count += 1
                continue
            if not self._is_restore_stale(artifact):
                skip_count += 1
                continue
            try:
                self._reset_stale_restore(artifact)
                reset_count += 1
            except BackupRestoreBlocked:
                skip_count += 1
            except Exception:
                error_count += 1
        return reset_count, skip_count, error_count

    @admin.display(description="Classification")
    def restore_scope_badge(self, obj: BackupArtifact) -> str:
        return obj.effective_restore_scope() or "unclassified"

    @admin.display(description="Stale restore")
    def stale_restore_warning(self, obj: BackupArtifact) -> str:
        """Show a staleness warning when a Status.RESTORING artifact is stale."""
        if obj.status != BackupArtifact.Status.RESTORING:
            return ""
        if not self._is_restore_stale(obj):
            return "In progress\u2026"
        return format_html(
            '<span style="color: #856404; font-weight: bold;">{}</span>',
            "\u26a0 Stale",
        )

    @admin.display(description="Snapshot status")
    def snapshot_status_badge(self, obj: BackupArtifact) -> str:
        snapshot_status = self._snapshot_status_value(obj)
        if snapshot_status is None:
            return "Untracked"

        return str(
            dict(BackupSnapshot.Status.choices).get(snapshot_status, snapshot_status)
        )

    @admin.display(description="Provenance")
    def snapshot_provenance(self, obj: BackupArtifact) -> str:
        source_environment = self._snapshot_source_environment_value(obj)
        snapshot_reference = self._snapshot_reference_value(obj)
        if source_environment and snapshot_reference:
            return f"{source_environment} ({snapshot_reference})"
        if source_environment:
            return source_environment
        if snapshot_reference:
            return snapshot_reference
        return "Untracked"

    @admin.display(description="Snapshot reference")
    def snapshot_reference(self, obj: BackupArtifact) -> str:
        return self._snapshot_reference_value(obj) or "Untracked"

    @admin.display(description="Source environment")
    def snapshot_source_environment(self, obj: BackupArtifact) -> str:
        return self._snapshot_source_environment_value(obj) or "Unavailable"

    @admin.display(description="Download")
    def download_link(self, obj: BackupArtifact) -> str:
        if not self._has_downloadable_local_file(obj):
            return "Unavailable"

        url = reverse(
            "admin:quickscale_backups_backupartifact_download",
            args=[obj.pk],
        )
        return format_html('<a class="button" href="{}">Download</a>', url)

    @admin.display(description="Download path")
    def download_path_display(self, obj: BackupArtifact) -> str:
        return obj.download_path() or "Unavailable"

    @admin.display(description="Storage location")
    def storage_location(self, obj: BackupArtifact) -> str:
        return obj.download_path() or "Unavailable"

    @admin.display(description="Admin availability")
    def admin_availability_notice(self, obj: BackupArtifact) -> str:
        if self._has_downloadable_local_file(obj):
            return (
                "Local file present. Admin download and validate can operate on "
                "this artifact."
            )
        if obj.local_path:
            return (
                "Local file missing. Admin download and validate remain local-file-"
                "only and cannot operate until the local artifact is present."
            )
        return (
            "No local file recorded. Admin download and validate remain local-file-"
            "only and do not materialize remote-only artifacts."
        )

    @admin.display(description="Metadata")
    def metadata_pretty(self, obj: BackupArtifact) -> str:
        return format_html(
            "<pre>{}</pre>",
            json.dumps(obj.metadata_json, indent=2, sort_keys=True),
        )

    @admin.display(description="Restore note")
    def restore_cli_notice(self, obj: BackupArtifact) -> str:
        if obj.is_export_only():
            classification_note = (
                "Classification: export_only. This artifact is export-only and is "
                "not a supported restore input."
            )
        elif obj.is_local_only():
            classification_note = (
                "Classification: local_only. This artifact is treated "
                "conservatively as local-only until portable compatibility is "
                "recorded."
            )
        elif obj.is_portable():
            classification_note = (
                "Classification: portable. This artifact is marked as a portable "
                "restore candidate."
            )
        else:
            classification_note = (
                "Classification: unclassified. No restore classification has been "
                "recorded for this artifact yet."
            )
        return (
            f"{classification_note} "
            "Admin download and validate only work when the local file is present. "
            "This BackupArtifact admin page remains download/validate-focused. For "
            "eligible row-backed local PostgreSQL dump artifacts already present on "
            "disk, use the guarded restore flow on the BackupPolicy admin page. Use "
            "'python manage.py quickscale_backups_restore <id> --confirm <filename>' or "
            "'python manage.py quickscale_backups_restore --file /path/to/backup.dump --confirm "
            "backup.dump' for artifact-id and operator-supplied file-path restores "
            "outside that admin surface."
        )

    @admin.action(description="Validate selected backups")
    def validate_selected_backups(self, request: HttpRequest, queryset: Any) -> None:
        """Validate selected artifacts and report any failures."""
        issues_found = 0
        for artifact in queryset:
            issues = self._validate_backup_artifact(artifact)
            if issues:
                issues_found += 1

        if issues_found:
            self.message_user(
                request,
                f"Validation completed with {issues_found} failing artifact(s).",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                "All selected backup artifacts validated successfully.",
                level=messages.SUCCESS,
            )

    @admin.action(
        description="Reset stale restore",
        permissions=["change"],
    )
    def reset_stale_restore_action(
        self,
        request: HttpRequest,
        queryset: Any,
    ) -> None:
        """Reset stranded Status.RESTORING artifacts that exceed the stale threshold."""
        reset_count, skip_count, error_count = self._reset_stale_artifacts(queryset)
        self.message_user(
            request,
            _reset_stale_summary(reset_count, skip_count, error_count),
            level=(
                messages.SUCCESS
                if reset_count and not error_count
                else messages.WARNING
            ),
        )

    def delete_model(self, request: HttpRequest, obj: BackupArtifact) -> None:
        """Delete local and remote files before removing artifact metadata."""
        self._delete_artifact_files(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: Any) -> None:
        """Delete local and remote files before bulk metadata deletion."""
        for artifact in queryset:
            self._delete_artifact_files(artifact)
        super().delete_queryset(request, queryset)
