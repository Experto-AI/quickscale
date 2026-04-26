"""Admin configuration for QuickScale backups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from quickscale_modules_backups.models import BackupArtifact, BackupPolicy
from quickscale_modules_backups.services import (
    BackupError,
    RestoreSourceResolutionMode,
    create_backup,
    delete_artifact_files,
    download_backup_path,
    ensure_default_policy,
    prune_expired_backups,
    restore_backup_artifact,
    validate_backup_artifact,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


class BackupPolicyRestoreForm(forms.Form):
    """Collect the selected local artifact and exact filename confirmation."""

    artifact_id = forms.IntegerField(
        label="Eligible local artifact",
        min_value=1,
        widget=forms.Select(),
        help_text=(
            "Choose a row-backed PostgreSQL dump artifact whose local file is "
            "already present on disk."
        ),
    )
    confirmation = forms.CharField(
        label="Exact artifact filename",
        strip=False,
        help_text=(
            "Type the exact filename of the selected artifact before dry-run "
            "validation or restore can continue."
        ),
    )

    def __init__(
        self,
        *args: Any,
        artifact_choices: list[tuple[int, str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["artifact_id"].widget.choices = [
            ("", "Select an eligible local backup artifact"),
            *artifact_choices,
        ]


@admin.register(BackupPolicy)
class BackupPolicyAdmin(admin.ModelAdmin):
    """Read-only admin interface for the applied backup policy snapshot."""

    _notice_fields = [
        "authoritative_source_notice",
        "command_driven_notice",
        "restore_notice",
    ]
    _change_required_actions = frozenset(
        {"create_backup_now", "prune_expired_backups_now"}
    )

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
    restore_template_name = "admin/quickscale_modules_backups/backuppolicy/restore.html"

    def get_urls(self) -> list[Any]:
        """Add explicit operator endpoints for backup creation, restore, and pruning."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops/create/",
                self.admin_site.admin_view(self.create_backup_view),
                name="quickscale_modules_backups_backuppolicy_create",
            ),
            path(
                "ops/restore/",
                self.admin_site.admin_view(self.restore_backup_view),
                name="quickscale_modules_backups_backuppolicy_restore",
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

    def _require_change_permission(self, request: HttpRequest) -> None:
        """Require BackupPolicy change permission for mutating admin operations."""
        if not self.has_change_permission(request):
            raise PermissionDenied

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Ensure the default policy exists before rendering the changelist."""
        requested_action = request.POST.get("action")
        if (
            request.method == "POST"
            and requested_action in self._change_required_actions
        ):
            self._require_change_permission(request)

        ensure_default_policy()
        merged_context = {
            **(extra_context or {}),
            "show_create_prune_controls": self.has_change_permission(request),
            "show_restore_control": self.has_view_or_change_permission(request),
        }
        return super().changelist_view(request, merged_context)

    def create_backup_view(self, request: HttpRequest) -> HttpResponseRedirect:
        """Run backup creation from a dedicated admin endpoint."""
        self._require_change_permission(request)
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
        self._require_change_permission(request)
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
            )
        self.prune_expired_backups_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
        )

    def restore_backup_view(self, request: HttpRequest) -> HttpResponse:
        """Render and execute the guarded local-artifact restore workflow."""
        if request.method == "POST":
            if not self.has_change_permission(request):
                raise PermissionDenied
        elif not self.has_view_or_change_permission(request):
            raise PermissionDenied

        policy = ensure_default_policy()
        eligible_artifacts = self._get_admin_restore_candidates()
        form = BackupPolicyRestoreForm(
            artifact_choices=self._build_restore_artifact_choices(eligible_artifacts)
        )
        selected_artifact: BackupArtifact | None = None

        if request.method == "POST":
            form = BackupPolicyRestoreForm(
                request.POST,
                artifact_choices=self._build_restore_artifact_choices(
                    eligible_artifacts
                ),
            )
            posted_artifact_id = self._parse_restore_artifact_id(
                request.POST.get("artifact_id")
            )
            selected_artifact = self._get_restore_artifact_by_id(posted_artifact_id)

            if not eligible_artifacts:
                form.add_error(
                    None,
                    "No eligible local backup artifacts are currently available for admin restore.",
                )

            if posted_artifact_id is not None and selected_artifact is None:
                form.add_error(
                    "artifact_id",
                    "The selected backup artifact no longer exists.",
                )
            elif selected_artifact is not None:
                ineligible_reason = self._get_admin_restore_ineligible_reason(
                    selected_artifact
                )
                if ineligible_reason is not None:
                    form.add_error("artifact_id", ineligible_reason)

            operation = request.POST.get("operation")
            if operation not in {"dry_run", "restore"}:
                form.add_error(
                    None,
                    "Choose either dry-run validation or restore before continuing.",
                )

            if (
                form.is_valid()
                and selected_artifact is not None
                and operation is not None
            ):
                try:
                    result = restore_backup_artifact(
                        selected_artifact,
                        confirmation=form.cleaned_data["confirmation"],
                        dry_run=operation == "dry_run",
                        resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
                    )
                except BackupError as exc:
                    form.add_error(None, str(exc))
                else:
                    self.message_user(
                        request,
                        result.message,
                        level=messages.SUCCESS,
                    )
                    for warning in result.warnings:
                        self.message_user(
                            request,
                            warning.message,
                            level=messages.WARNING,
                        )

                    if operation == "dry_run":
                        return HttpResponseRedirect(
                            f"{reverse('admin:quickscale_modules_backups_backuppolicy_restore')}"
                            f"?artifact_id={selected_artifact.pk}"
                        )
                    return HttpResponseRedirect(
                        reverse(
                            "admin:quickscale_modules_backups_backuppolicy_changelist"
                        )
                    )
        else:
            selected_artifact = self._get_restore_artifact_by_id(
                self._parse_restore_artifact_id(request.GET.get("artifact_id"))
            )
            initial_artifact_id = (
                selected_artifact.pk if selected_artifact is not None else None
            )
            if initial_artifact_id is not None:
                form = BackupPolicyRestoreForm(
                    initial={"artifact_id": initial_artifact_id},
                    artifact_choices=self._build_restore_artifact_choices(
                        eligible_artifacts
                    ),
                )

        change_url = reverse(
            "admin:quickscale_modules_backups_backuppolicy_change",
            args=[policy.pk],
        )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Restore backup artifact",
            "form": form,
            "policy": policy,
            "change_url": change_url,
            "changelist_url": reverse(
                "admin:quickscale_modules_backups_backuppolicy_changelist"
            ),
            "eligible_artifacts": eligible_artifacts,
            "selected_artifact": selected_artifact,
        }
        return TemplateResponse(request, self.restore_template_name, context)

    def _build_restore_artifact_choices(
        self,
        artifacts: list[BackupArtifact],
    ) -> list[tuple[int, str]]:
        """Build the select options for eligible local restore artifacts."""
        return [
            (
                int(artifact.pk),
                (
                    f"{artifact.filename}"
                    f" ({artifact.restore_scope_label()}, {artifact.created_at:%Y-%m-%d %H:%M:%S})"
                ),
            )
            for artifact in artifacts
            if artifact.pk is not None
        ]

    def _get_admin_restore_candidates(self) -> list[BackupArtifact]:
        """Return the current admin-eligible local restore artifacts."""
        artifacts = BackupArtifact.objects.order_by("-created_at")
        return [
            artifact
            for artifact in artifacts
            if self._get_admin_restore_ineligible_reason(artifact) is None
        ]

    def _get_admin_restore_ineligible_reason(
        self,
        artifact: BackupArtifact,
    ) -> str | None:
        """Return why an artifact cannot be restored from the admin surface."""
        if artifact.status == BackupArtifact.STATUS_DELETED:
            return "Deleted backup artifacts cannot be restored from admin."
        if artifact.is_export_only() or artifact.backup_format != "pg_dump_custom":
            return (
                "Admin restore only supports PostgreSQL custom-format backup artifacts."
            )
        if artifact.effective_restore_scope() not in {
            BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
            BackupArtifact.RESTORE_SCOPE_PORTABLE,
        }:
            return "This backup artifact is not classified as an eligible restore candidate."
        if not artifact.local_path:
            return "Admin restore only supports row-backed local artifacts already present on disk."
        if not Path(artifact.local_path).exists():
            return (
                "The selected local backup artifact is no longer present on disk, and "
                "admin restore will not materialize remote-only artifacts."
            )
        return None

    def _get_restore_artifact_by_id(
        self,
        artifact_id: int | None,
    ) -> BackupArtifact | None:
        """Re-fetch one artifact row by id for each admin restore request."""
        if artifact_id is None:
            return None
        return BackupArtifact.objects.filter(pk=artifact_id).first()

    def _parse_restore_artifact_id(self, value: str | None) -> int | None:
        """Parse the selected artifact id from the request payload."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
            "Guarded admin restore is available only from the BackupPolicy change "
            "list for row-backed local PostgreSQL dump artifacts that are already "
            "present on disk. Operators must choose an eligible artifact, re-enter "
            "the exact filename, and satisfy the existing environment gate. Remote-"
            "only artifacts are never materialized through admin, and CLI restore "
            "keeps its current artifact-id and --file PATH entrypoints under the "
            "same guardrails."
        )

    @admin.action(description="Create backup now", permissions=["change"])
    def create_backup_now(self, request: HttpRequest, queryset: Any) -> None:
        """Create a new backup artifact from the admin surface."""
        self._require_change_permission(request)
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

    @admin.action(description="Prune expired backups now", permissions=["change"])
    def prune_expired_backups_now(self, request: HttpRequest, queryset: Any) -> None:
        """Prune expired backup files and mark their metadata as deleted."""
        self._require_change_permission(request)
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
        "restore_scope_badge",
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
        "restore_scope_badge",
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

    def _require_view_or_change_permission(self, request: HttpRequest) -> None:
        """Require BackupArtifact view or change permission for admin downloads."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

    def _has_downloadable_local_file(self, obj: BackupArtifact) -> bool:
        """Return whether the admin can still offer a local download action."""
        if obj.status == BackupArtifact.STATUS_DELETED:
            return False
        if not obj.local_path:
            return False
        return Path(obj.local_path).exists()

    @admin.display(description="Classification")
    def restore_scope_badge(self, obj: BackupArtifact) -> str:
        return obj.effective_restore_scope() or "unclassified"

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
            "'python manage.py backups_restore <id> --confirm <filename>' or "
            "'python manage.py backups_restore --file /path/to/backup.dump --confirm "
            "backup.dump' for artifact-id and operator-supplied file-path restores "
            "outside that admin surface."
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
        self._require_view_or_change_permission(request)
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
