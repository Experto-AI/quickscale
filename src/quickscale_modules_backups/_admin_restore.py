"""Restore-workflow helpers for the backups admin surface.

``BackupPolicyAdmin`` in ``quickscale_modules_backups.admin`` mixes this
implementation in and overrides the service-call seams
(``_resolve_dry_run_result`` and ``_dispatch_restore``) so the
``quickscale_modules_backups.services`` module stays the lookup site for the
restore service calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from quickscale_modules_backups._admin_forms import BackupPolicyRestoreForm
from quickscale_modules_backups.models import BackupArtifact, BackupPolicy
from quickscale_modules_backups.services import BackupError


class RestoreWorkflowAdminMixin(admin.ModelAdmin):
    """Guarded restore page implementation shared into ``BackupPolicyAdmin``."""

    restore_template_name = "admin/quickscale_backups/backuppolicy/restore.html"

    def _require_restore_access(self, request: HttpRequest) -> None:
        """Require the permission the restore payload's method demands."""
        if request.method == "POST":
            if not self.has_change_permission(request):
                raise PermissionDenied
            return
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

    def _build_restore_form(
        self,
        request: HttpRequest,
        eligible_artifacts: list[BackupArtifact],
        can_view_restore_artifacts: bool,
        selected_artifact: BackupArtifact | None = None,
    ) -> BackupPolicyRestoreForm:
        """Build the restore form for the request phase and selected artifact."""
        artifact_choices = self._build_restore_artifact_choices(eligible_artifacts)
        if request.method == "POST":
            return BackupPolicyRestoreForm(
                request.POST,
                request.FILES,
                artifact_choices=artifact_choices,
                allow_recorded_artifact_source=can_view_restore_artifacts,
            )
        initial = (
            {"artifact_id": selected_artifact.pk}
            if selected_artifact is not None
            else None
        )
        return BackupPolicyRestoreForm(
            initial=initial,
            artifact_choices=artifact_choices,
            allow_recorded_artifact_source=can_view_restore_artifacts,
        )

    def _select_restore_artifact_from_query(
        self,
        request: HttpRequest,
        can_view_restore_artifacts: bool,
    ) -> BackupArtifact | None:
        """Resolve the ``artifact_id`` query selection for the GET form."""
        if not can_view_restore_artifacts:
            return None
        artifact_id = self._parse_restore_artifact_id(request.GET.get("artifact_id"))
        return self._get_restore_artifact_by_id(artifact_id)

    def _is_restore_stale(self, artifact: BackupArtifact) -> bool:
        """Return whether the artifact's restore is stale.

        Implemented on the registered admin class, which keeps the service
        lookup on the services module.
        """
        raise NotImplementedError

    def _handle_restore_post(
        self,
        request: HttpRequest,
        form: BackupPolicyRestoreForm,
        eligible_artifacts: list[BackupArtifact],
        can_view_restore_artifacts: bool,
    ) -> tuple[HttpResponse | None, BackupArtifact | None]:
        """Process one restore POST.

        Returns the response when the request completed, together with the
        resolved recorded-artifact selection so a rendered error page keeps
        its selection banner.
        """
        operation = request.POST.get("operation")
        if operation not in {"dry_run", "restore"}:
            form.add_error(
                None,
                "Choose either dry-run validation or restore before continuing.",
            )

        selected_artifact: BackupArtifact | None = None
        if form.is_valid() and operation is not None:
            selected_artifact = self._resolve_recorded_restore_selection(
                form,
                eligible_artifacts,
                can_view_restore_artifacts,
            )
            if not form.errors:
                if operation == "dry_run":
                    return (
                        self._run_restore_dry_run(request, form, selected_artifact),
                        selected_artifact,
                    )
                return (
                    self._run_restore_dispatch(request, form, selected_artifact),
                    selected_artifact,
                )
        return None, selected_artifact

    def _resolve_recorded_restore_selection(
        self,
        form: BackupPolicyRestoreForm,
        eligible_artifacts: list[BackupArtifact],
        can_view_restore_artifacts: bool,
    ) -> BackupArtifact | None:
        """Resolve the recorded-artifact branch, adding form errors as needed."""
        source_mode = form.cleaned_data.get("source_mode")
        if source_mode != BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT:
            return None
        if not can_view_restore_artifacts:
            form.add_error(
                "source_mode",
                "Recorded local artifacts are unavailable for your current permissions.",
            )
            return None

        artifact_id = form.cleaned_data["artifact_id"]
        selected_artifact = self._get_restore_artifact_by_id(artifact_id)
        if artifact_id is not None and selected_artifact is None:
            form.add_error(
                "artifact_id",
                "The selected backup artifact no longer exists.",
            )
            return None
        if selected_artifact is None:
            if not eligible_artifacts:
                form.add_error(
                    None,
                    "No eligible local backup artifacts are currently available for admin restore.",
                )
            return None

        ineligible_reason = self._get_admin_restore_ineligible_reason(selected_artifact)
        if ineligible_reason is not None:
            form.add_error("artifact_id", ineligible_reason)
        return selected_artifact

    def _run_restore_dry_run(
        self,
        request: HttpRequest,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> HttpResponse | None:
        """Run dry-run validation and report its result, or add the failure."""
        try:
            result = self._resolve_dry_run_result(form, selected_artifact)
        except BackupError as exc:
            form.add_error(None, str(exc))
            return None

        self._report_restore_messages(request, result)
        redirect_url = reverse("admin:quickscale_backups_backuppolicy_restore")
        if selected_artifact is not None:
            redirect_url = f"{redirect_url}?artifact_id={selected_artifact.pk}"
        return HttpResponseRedirect(redirect_url)

    def _resolve_dry_run_result(
        self,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> Any:
        """Call the dry-run restore service for the selected source mode.

        Implemented on the registered admin class, which keeps the restore
        service lookup on the services module.
        """
        raise NotImplementedError

    def _run_restore_dispatch(
        self,
        request: HttpRequest,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> HttpResponse | None:
        """Dispatch a background restore and report the outcome."""
        try:
            self._dispatch_restore(form, selected_artifact)
        except Exception as exc:
            form.add_error(
                None,
                f"Failed to initiate background restore: {exc}",
            )
            return None

        self.message_user(
            request,
            "Restore has been initiated in the background. "
            "Check the artifact's status for progress or errors.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(
            reverse("admin:quickscale_backups_backuppolicy_changelist")
        )

    def _dispatch_restore(
        self,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
    ) -> None:
        """Dispatch the recorded-artifact or uploaded-file restore path.

        Implemented on the registered admin class, which keeps the restore
        service lookup on the services module.
        """
        raise NotImplementedError

    def _report_restore_messages(self, request: HttpRequest, result: Any) -> None:
        """Report one restore result's message and warnings to the operator."""
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

    def _render_restore_response(
        self,
        request: HttpRequest,
        *,
        policy: BackupPolicy,
        form: BackupPolicyRestoreForm,
        selected_artifact: BackupArtifact | None,
        eligible_artifacts: list[BackupArtifact],
        can_view_restore_artifacts: bool,
    ) -> HttpResponse:
        """Render the guarded restore page for the current request state."""
        change_url = reverse(
            "admin:quickscale_backups_backuppolicy_change",
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
                "admin:quickscale_backups_backuppolicy_changelist"
            ),
            "can_view_restore_artifacts": can_view_restore_artifacts,
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
        if artifact.status == BackupArtifact.Status.DELETED:
            return "Deleted backup artifacts cannot be restored from admin."
        if artifact.status == BackupArtifact.Status.RESTORING:
            if self._is_restore_stale(artifact):
                return (
                    "This backup artifact's restore appears stale "
                    f"(started at {artifact.restore_started_at:%Y-%m-%d %H:%M:%S} UTC) — "
                    "the child process likely died. Reset the artifact status "
                    "from the BackupArtifact admin list to retry."
                )
            return (
                "This backup artifact is currently being restored. "
                "Wait for the restore to complete before retrying."
            )
        if artifact.is_export_only() or artifact.backup_format != "pg_dump_custom":
            return (
                "Admin restore only supports PostgreSQL custom-format backup artifacts."
            )
        if artifact.effective_restore_scope() not in {
            BackupArtifact.RestoreScope.LOCAL_ONLY,
            BackupArtifact.RestoreScope.PORTABLE,
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
        except TypeError:
            return None
        except ValueError:
            return None
