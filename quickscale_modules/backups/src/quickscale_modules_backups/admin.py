"""Admin configuration for QuickScale backups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.contrib import admin, messages
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from quickscale_modules_backups.models import BackupArtifact, BackupPolicy
from quickscale_modules_backups.services import (
    BackupError,
    create_backup,
    delete_artifact_files,
    download_backup_path,
    ensure_default_policy,
    prune_expired_backups,
    validate_backup_artifact,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


@admin.register(BackupPolicy)
class BackupPolicyAdmin(admin.ModelAdmin):
    """Read-only admin interface for the applied backup policy snapshot."""

    _notice_fields = [
        "authoritative_source_notice",
        "command_driven_notice",
        "restore_notice",
    ]

    list_display = [
        "key",
        "target_mode",
        "retention_days",
        "automation_enabled",
        "schedule",
        "updated_at",
    ]
    fieldsets = [
        (
            "Applied policy snapshot",
            {
                "fields": [
                    "authoritative_source_notice",
                    "key",
                    "retention_days",
                    "naming_prefix",
                    "target_mode",
                    "local_directory",
                ],
                "description": (
                    "Runtime backup behavior is controlled by generated settings and "
                    "the apply-authoritative workflow. This admin page mirrors the "
                    "effective snapshot for operator visibility only."
                ),
            },
        ),
        (
            "Private remote offload snapshot",
            {
                "fields": [
                    "remote_bucket_name",
                    "remote_prefix",
                    "remote_endpoint_url",
                    "remote_region_name",
                    "remote_access_key_id_env_var",
                    "remote_secret_access_key_env_var",
                ],
                "classes": ["collapse"],
                "description": (
                    "Only used when target mode is private_remote. Configure the "
                    "named environment variables in the runtime environment; raw "
                    "credentials are never stored in the database."
                ),
            },
        ),
        (
            "Admin operations",
            {
                "fields": [
                    "automation_enabled",
                    "schedule",
                    "command_driven_notice",
                    "restore_notice",
                ]
            },
        ),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]
    actions = ["create_backup_now", "prune_expired_backups_now"]
    change_list_template = (
        "admin/quickscale_modules_backups/backuppolicy/change_list.html"
    )

    def get_urls(self) -> list[Any]:
        """Add explicit operator endpoints for backup creation and pruning."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops/create/",
                self.admin_site.admin_view(self.create_backup_view),
                name="quickscale_modules_backups_backuppolicy_create",
            ),
            path(
                "ops/prune/",
                self.admin_site.admin_view(self.prune_expired_backups_view),
                name="quickscale_modules_backups_backuppolicy_prune",
            ),
        ]
        return custom_urls + urls

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Policy rows are materialized from settings, never added in admin."""
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: BackupPolicy | None = None,
    ) -> bool:
        """Policy rows are managed by the apply/settings contract, not admin."""
        return False

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: BackupPolicy | None = None,
    ) -> list[str]:
        """Expose the policy as a read-only runtime snapshot."""
        model_fields = [field.name for field in self.model._meta.fields]
        return [*model_fields, *self._notice_fields]

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Ensure the default policy exists before rendering the changelist."""
        ensure_default_policy()
        return super().changelist_view(request, extra_context)

    def create_backup_view(self, request: HttpRequest) -> HttpResponseRedirect:
        """Run backup creation from a dedicated admin endpoint."""
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
            )
        self.create_backup_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
        )

    def prune_expired_backups_view(self, request: HttpRequest) -> HttpResponseRedirect:
        """Run backup pruning from a dedicated admin endpoint."""
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
            )
        self.prune_expired_backups_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
        )

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Hide save/delete controls because the policy view is informational."""
        merged_context = {
            **(extra_context or {}),
            "show_save": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": False,
            "show_delete": False,
        }
        return super().change_view(
            request,
            object_id,
            form_url=form_url,
            extra_context=merged_context,
        )

    @admin.display(description="Authoritative source")
    def authoritative_source_notice(self, obj: BackupPolicy) -> str:
        return (
            "Edit backup settings in quickscale.yml and re-run 'quickscale apply'. "
            "The generated Django settings remain authoritative at runtime, and "
            "this admin record is a read-only snapshot of those values."
        )

    @admin.display(description="Automation note")
    def command_driven_notice(self, obj: BackupPolicy) -> str:
        return (
            "Scheduled execution remains command-driven only. Use platform cron or "
            "scheduled jobs that call 'python manage.py backups_create --scheduled'."
        )

    @admin.display(description="Restore safety")
    def restore_notice(self, obj: BackupPolicy) -> str:
        return (
            "Destructive restore execution is intentionally CLI-only. Admin users can "
            "validate and download artifacts, but restore requires explicit CLI "
            "confirmation and environment guards."
        )

    @admin.action(description="Create backup now")
    def create_backup_now(self, request: HttpRequest, queryset: Any) -> None:
        """Create a new backup artifact from the admin surface."""
        initiated_by: AbstractBaseUser | None = None
        if request.user.is_authenticated:
            initiated_by = request.user
        try:
            artifact = create_backup(initiated_by=initiated_by, trigger="admin")
        except BackupError as exc:
            self.message_user(
                request, f"Backup creation failed: {exc}", level=messages.ERROR
            )
            return

        self.message_user(
            request,
            f"Created backup artifact {artifact.filename}",
            level=messages.SUCCESS,
        )

    @admin.action(description="Prune expired backups now")
    def prune_expired_backups_now(self, request: HttpRequest, queryset: Any) -> None:
        """Prune expired backup files and mark their metadata as deleted."""
        deleted_count = prune_expired_backups()
        self.message_user(
            request,
            f"Pruned {deleted_count} expired backup artifact(s).",
            level=messages.SUCCESS,
        )


@admin.register(BackupArtifact)
class BackupArtifactAdmin(admin.ModelAdmin):
    """Admin interface for backup artifact history and download access."""

    list_display = [
        "filename",
        "status",
        "storage_target",
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
        "storage_target",
        "local_path",
        "remote_key",
        "checksum_sha256",
        "size_bytes",
        "backup_format",
        "database_engine",
        "database_name",
        "metadata_pretty",
        "status",
        "trigger",
        "initiated_by",
        "validation_notes",
        "validated_at",
        "restored_at",
        "deleted_at",
        "created_at",
        "updated_at",
        "download_path_display",
        "download_link",
        "restore_cli_notice",
    ]
    fieldsets = [
        (
            "Artifact",
            {
                "fields": [
                    "filename",
                    "status",
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
                    "validation_notes",
                    "validated_at",
                    "restored_at",
                    "deleted_at",
                    "metadata_pretty",
                    "restore_cli_notice",
                ]
            },
        ),
    ]
    actions = ["validate_selected_backups"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Artifacts are created through commands or the policy admin."""
        return False

    def get_urls(self) -> list[Any]:
        """Add a staff-protected download endpoint for local backup files."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:artifact_id>/download/",
                self.admin_site.admin_view(self.download_view),
                name="quickscale_modules_backups_backupartifact_download",
            )
        ]
        return custom_urls + urls

    def _has_downloadable_local_file(self, obj: BackupArtifact) -> bool:
        """Return whether the admin can still offer a local download action."""
        if obj.status == BackupArtifact.STATUS_DELETED:
            return False
        if not obj.local_path:
            return False
        return Path(obj.local_path).exists()

    @admin.display(description="Download")
    def download_link(self, obj: BackupArtifact) -> str:
        if not self._has_downloadable_local_file(obj):
            return "Unavailable"

        url = reverse(
            "admin:quickscale_modules_backups_backupartifact_download",
            args=[obj.pk],
        )
        return format_html('<a class="button" href="{}">Download</a>', url)

    @admin.display(description="Download path")
    def download_path_display(self, obj: BackupArtifact) -> str:
        return obj.download_path() or "Unavailable"

    @admin.display(description="Metadata")
    def metadata_pretty(self, obj: BackupArtifact) -> str:
        return format_html(
            "<pre>{}</pre>",
            json.dumps(obj.metadata_json, indent=2, sort_keys=True),
        )

    @admin.display(description="Restore note")
    def restore_cli_notice(self, obj: BackupArtifact) -> str:
        return (
            "Use 'python manage.py backups_restore <id> --confirm <filename>' for "
            "destructive restores. Admin intentionally does not execute restores."
        )

    @admin.action(description="Validate selected backups")
    def validate_selected_backups(self, request: HttpRequest, queryset: Any) -> None:
        """Validate selected artifacts and report any failures."""
        issues_found = 0
        for artifact in queryset:
            issues = validate_backup_artifact(artifact)
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

    def delete_model(self, request: HttpRequest, obj: BackupArtifact) -> None:
        """Delete local and remote files before removing artifact metadata."""
        delete_artifact_files(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: Any) -> None:
        """Delete local and remote files before bulk metadata deletion."""
        for artifact in queryset:
            delete_artifact_files(artifact)
        super().delete_queryset(request, queryset)

    def download_view(
        self,
        request: HttpRequest,
        artifact_id: int,
    ) -> FileResponse | HttpResponseRedirect:
        """Stream a local backup file to authenticated staff users."""
        artifact = self.get_object(request, str(artifact_id))
        if artifact is None:
            self.message_user(
                request, "Backup artifact not found.", level=messages.ERROR
            )
            return HttpResponseRedirect(
                reverse("admin:quickscale_modules_backups_backupartifact_changelist")
            )

        if not self._has_downloadable_local_file(artifact):
            self.message_user(
                request,
                "Download unavailable: this artifact is no longer available.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:quickscale_modules_backups_backupartifact_change",
                    args=[artifact.pk],
                )
            )

        try:
            local_path = download_backup_path(artifact)
        except BackupError as exc:
            self.message_user(
                request, f"Download unavailable: {exc}", level=messages.ERROR
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:quickscale_modules_backups_backupartifact_change",
                    args=[artifact.pk],
                )
            )

        response = FileResponse(
            local_path.open("rb"), as_attachment=True, filename=artifact.filename
        )
        return response
