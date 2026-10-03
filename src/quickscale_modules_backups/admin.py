"""Admin configuration for QuickScale backups.

The restore form lives in ``_admin_forms``, the restore page helpers in
``_admin_restore``, and the artifact admin implementation in
``_admin_artifact``; this module re-exports its intended public surface so the
import path stays a drop-in replacement, and resolves service calls through
``quickscale_modules_backups.services`` at call time.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import path, reverse

import quickscale_modules_backups.services as _services

from quickscale_modules_backups._admin_artifact import BackupArtifactAdminBase
from quickscale_modules_backups._admin_forms import BackupPolicyRestoreForm
from quickscale_modules_backups._admin_restore import RestoreWorkflowAdminMixin
from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    STALE_RESTORE_THRESHOLD_MINUTES as STALE_RESTORE_THRESHOLD_MINUTES,
    BackupError as BackupError,
    BackupRestoreBlocked as BackupRestoreBlocked,
    RestoreSourceResolutionMode as RestoreSourceResolutionMode,
    delete_artifact_files as delete_artifact_files,
    dispatch_background_create as dispatch_background_create,
    dispatch_background_prune as dispatch_background_prune,
    dispatch_background_restore as dispatch_background_restore,
    download_backup_path as download_backup_path,
    ensure_default_policy as ensure_default_policy,
    is_restore_stale as is_restore_stale,
    prepare_admin_uploaded_restore_artifact as prepare_admin_uploaded_restore_artifact,
    reset_stale_restore as reset_stale_restore,
    restore_admin_uploaded_backup as restore_admin_uploaded_backup,
    restore_backup_artifact as restore_backup_artifact,
    validate_backup_artifact as validate_backup_artifact,
)

__all__ = [
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
]


@admin.register(BackupPolicy)
class BackupPolicyAdmin(RestoreWorkflowAdminMixin):
    """Read-only admin interface for the applied backup policy snapshot.

    The restore service-call seams resolve through
    ``quickscale_modules_backups.services`` at call time, so tests patch the
    module that defines each service.
    """

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
    change_list_template = "admin/quickscale_backups/backuppolicy/change_list.html"

    def get_urls(self) -> list[Any]:
        """Add explicit operator endpoints for backup creation, restore, and pruning."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "ops/create/",
                self.admin_site.admin_view(self.create_backup_view),
                name="quickscale_backups_backuppolicy_create",
            ),
            path(
                "ops/restore/",
                self.admin_site.admin_view(self.restore_backup_view),
                name="quickscale_backups_backuppolicy_restore",
            ),
            path(
                "ops/prune/",
                self.admin_site.admin_view(self.prune_expired_backups_view),
                name="quickscale_backups_backuppolicy_prune",
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

    def _get_artifact_admin(self) -> BackupArtifactAdmin | None:
        """Return the registered BackupArtifact admin when available."""
        artifact_admin = self.admin_site._registry.get(BackupArtifact)
        if isinstance(artifact_admin, BackupArtifactAdmin):
            return artifact_admin
        return None

    def _is_restore_stale(self, artifact: BackupArtifact) -> bool:
        """Return whether the artifact's restore is stale."""
        return _services.is_restore_stale(artifact)

    def _can_view_restore_artifacts(self, request: HttpRequest) -> bool:
        """Return whether this request may inspect artifact-backed restore inputs."""
        artifact_admin = self._get_artifact_admin()
        if artifact_admin is None:
            return False
        return artifact_admin.has_view_or_change_permission(request)

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

        _services.ensure_default_policy()
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
                reverse("admin:quickscale_backups_backuppolicy_changelist")
            )
        self.create_backup_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_backups_backuppolicy_changelist")
        )

    def prune_expired_backups_view(self, request: HttpRequest) -> HttpResponseRedirect:
        """Run backup pruning from a dedicated admin endpoint."""
        self._require_change_permission(request)
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:quickscale_backups_backuppolicy_changelist")
            )
        self.prune_expired_backups_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_backups_backuppolicy_changelist")
        )

    def restore_backup_view(self, request: HttpRequest) -> HttpResponse:
        """Render and execute the guarded admin restore workflow."""
        self._require_restore_access(request)

        policy = _services.ensure_default_policy()
        can_view_restore_artifacts = self._can_view_restore_artifacts(request)
        eligible_artifacts = (
            self._get_admin_restore_candidates() if can_view_restore_artifacts else []
        )
        selected_artifact: BackupArtifact | None = None

        if request.method == "POST":
            form = self._build_restore_form(
                request,
                eligible_artifacts,
                can_view_restore_artifacts,
            )
            response, selected_artifact = self._handle_restore_post(
                request,
                form,
                eligible_artifacts,
                can_view_restore_artifacts,
            )
            if response is not None:
                return response
        else:
            selected_artifact = self._select_restore_artifact_from_query(
                request,
                can_view_restore_artifacts,
            )
            form = self._build_restore_form(
                request,
                eligible_artifacts,
                can_view_restore_artifacts,
                selected_artifact=selected_artifact,
            )

        return self._render_restore_response(
            request,
            policy=policy,
            form=form,
            selected_artifact=selected_artifact,
            eligible_artifacts=eligible_artifacts,
            can_view_restore_artifacts=can_view_restore_artifacts,
        )

    def _resolve_dry_run_result(
        self,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> Any:
        """Call the dry-run restore service for the selected source mode."""
        if (
            form.cleaned_data["source_mode"]
            == BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT
        ):
            assert selected_artifact is not None  # noqa: S101 - internal invariant guaranteed by the caller
            return _services.restore_backup_artifact(
                selected_artifact,
                confirmation=form.cleaned_data["confirmation"],
                dry_run=True,
                resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
            )
        return _services.restore_admin_uploaded_backup(
            form.cleaned_data["uploaded_file"],
            confirmation=form.cleaned_data["confirmation"],
            dry_run=True,
            stale_threshold_minutes=STALE_RESTORE_THRESHOLD_MINUTES,
        )

    def _dispatch_restore(
        self,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> None:
        """Dispatch the recorded-artifact or uploaded-file restore path."""
        if (
            form.cleaned_data["source_mode"]
            == BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT
        ):
            assert selected_artifact is not None  # noqa: S101 - internal invariant guaranteed by the caller
            _services.dispatch_background_restore(
                selected_artifact,
                confirmation=form.cleaned_data["confirmation"],
            )
            return

        trusted_artifact = _services.prepare_admin_uploaded_restore_artifact(
            form.cleaned_data["uploaded_file"],
            confirmation=form.cleaned_data["confirmation"],
        )
        _services.dispatch_background_restore(
            trusted_artifact,
            confirmation=form.cleaned_data["confirmation"],
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
            "scheduled jobs that call 'python manage.py quickscale_backups_create --scheduled'."
        )

    @admin.display(description="Restore safety")
    def restore_notice(self, obj: BackupPolicy) -> str:
        return (
            "Guarded admin restore is available only from the BackupPolicy change "
            "list for PostgreSQL dump artifacts. Operators may either choose an "
            "eligible local artifact already present on disk or upload a dump file "
            "that resolves to exactly one trusted authoritative artifact by recorded "
            "checksum and size. Operators must still re-enter the exact filename for "
            "the authoritative artifact and satisfy the existing environment gate. "
            "Remote-only artifacts "
            "are never materialized through admin, and CLI restore keeps its current "
            "artifact-id, snapshot-id, and --file PATH entrypoints under the same "
            "guardrails."
        )

    @admin.action(description="Create backup now", permissions=["change"])
    def create_backup_now(self, request: HttpRequest, queryset: Any) -> None:
        """Dispatch background backup creation from the admin surface."""
        self._require_change_permission(request)
        try:
            _services.dispatch_background_create(trigger="admin")
        except BackupError as exc:
            self.message_user(
                request,
                f"Backup creation failed: {exc}",
                level=messages.ERROR,
            )
            return

        self.message_user(
            request,
            "Backup creation has been initiated in the background.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Prune expired backups now", permissions=["change"])
    def prune_expired_backups_now(self, request: HttpRequest, queryset: Any) -> None:
        """Dispatch background backup pruning from the admin surface."""
        self._require_change_permission(request)
        try:
            _services.dispatch_background_prune(trigger="admin")
        except BackupError as exc:
            self.message_user(
                request,
                f"Backup pruning failed: {exc}",
                level=messages.ERROR,
            )
            return

        self.message_user(
            request,
            "Backup pruning has been initiated in the background.",
            level=messages.SUCCESS,
        )


@admin.register(BackupArtifact)
class BackupArtifactAdmin(BackupArtifactAdminBase):
    """Admin interface for backup artifact history and download access.

    The service-call seams resolve through
    ``quickscale_modules_backups.services`` at call time, so tests patch the
    module that defines each service.
    """

    def _get_policy_admin(self) -> BackupPolicyAdmin | None:
        """Return the registered BackupPolicy admin when available."""
        policy_admin = self.admin_site._registry.get(BackupPolicy)
        if isinstance(policy_admin, BackupPolicyAdmin):
            return policy_admin
        return None

    def _is_restore_stale(self, artifact: BackupArtifact) -> bool:
        """Return whether the artifact's restore is stale."""
        return _services.is_restore_stale(artifact)

    def _reset_stale_restore(self, artifact: BackupArtifact) -> None:
        """Reset one stranded restore to ``Status.FAILED``."""
        _services.reset_stale_restore(artifact)

    def _validate_backup_artifact(self, artifact: BackupArtifact) -> Any:
        """Validate one artifact and return its issues."""
        return _services.validate_backup_artifact(artifact)

    def _delete_artifact_files(self, artifact: BackupArtifact) -> None:
        """Delete one artifact's local and remote files."""
        _services.delete_artifact_files(artifact)

    def _has_downloadable_local_file(self, obj: BackupArtifact) -> bool:
        """Return whether the admin can still offer a local download action."""
        if obj.status == BackupArtifact.Status.DELETED:
            return False

        try:
            _services.download_backup_path(obj)
        except BackupError:
            return False
        return True

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
                reverse("admin:quickscale_backups_backupartifact_changelist")
            )

        if not self._has_downloadable_local_file(artifact):
            self.message_user(
                request,
                "Download unavailable: this artifact is no longer available.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:quickscale_backups_backupartifact_change",
                    args=[artifact.pk],
                )
            )

        try:
            local_path = _services.download_backup_path(artifact)
        except BackupError as exc:
            self.message_user(
                request, f"Download unavailable: {exc}", level=messages.ERROR
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:quickscale_backups_backupartifact_change",
                    args=[artifact.pk],
                )
            )

        response = FileResponse(
            local_path.open("rb"), as_attachment=True, filename=artifact.filename
        )
        return response
