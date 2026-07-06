"""Admin configuration for QuickScale backups."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone as django_timezone
from django.utils.html import format_html

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    BackupError,
    BackupRestoreBlocked,
    RestoreSourceResolutionMode,
    # Admin uploaded-file staging/resolution/cleanup seam
    _cleanup_admin_restore_upload_directory,
    _resolve_admin_uploaded_restore_artifact,
    _stage_admin_restore_upload,
    create_backup,
    delete_artifact_files,
    download_backup_path,
    ensure_default_policy,
    get_local_backup_directory,
    load_policy_snapshot,
    prune_expired_backups,
    restore_admin_uploaded_backup,
    restore_backup_artifact,
    validate_backup_artifact,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


_ARTIFACT_RESTORE_CLAIMABLE_STATUSES: frozenset[str] = frozenset(
    {
        BackupArtifact.STATUS_READY,
        BackupArtifact.STATUS_VALIDATED,
        BackupArtifact.STATUS_FAILED,
        BackupArtifact.STATUS_RESTORED,
    }
)
"""Pre-claim statuses eligible for an atomic restore claim.

Excludes STATUS_DELETED (terminal — never restorable) and
STATUS_RESTORING (already claimed by another request).
"""


def _atomic_claim_restore(artifact: BackupArtifact) -> bool:
    """Atomically claim *artifact* for restore via DB compare-and-swap.

    Uses a single filtered ``update()`` to transition the artifact from an
    eligible pre-claim status to ``STATUS_RESTORING``.  Only the caller that
    wins the race sees ``updated > 0``; losers re-read the artifact and
    return ``False``.

    After a successful claim the in-memory *artifact* is refreshed from the
    database so its attributes reflect ``STATUS_RESTORING`` /
    ``restore_started_at`` / ``restore_error``.  After a failed claim the
    in-memory *artifact* is also refreshed so the caller can inspect the
    current status to surface an appropriate reason.

    Callers **must** snapshot ``artifact.status``, ``restore_started_at``,
    and ``restore_error`` *before* calling this function if they need to
    roll back on a subsequent spawn failure.
    """
    now = django_timezone.now()
    updated = BackupArtifact.objects.filter(
        pk=artifact.pk,
        status__in=_ARTIFACT_RESTORE_CLAIMABLE_STATUSES,
    ).update(
        status=BackupArtifact.STATUS_RESTORING,
        restore_started_at=now,
        restore_error="",
        updated_at=now,
    )
    artifact.refresh_from_db()
    return updated > 0


def _get_manage_py() -> str:
    """Return the path to manage.py for subprocess management-command dispatch."""
    script = Path(sys.argv[0])
    if script.name == "manage.py" and script.exists():
        return str(script)
    try:
        from django.conf import settings

        base = Path(settings.BASE_DIR)
        candidate = base / "manage.py"
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return "manage.py"


class BackupPolicyRestoreForm(forms.Form):
    """Collect either a local artifact or uploaded file plus exact confirmation."""

    SOURCE_MODE_RECORDED_ARTIFACT = "recorded_artifact"
    SOURCE_MODE_UPLOADED_FILE = "uploaded_file"

    source_mode = forms.ChoiceField(
        label="Restore source",
        required=False,
        choices=[
            (SOURCE_MODE_RECORDED_ARTIFACT, "Recorded local artifact"),
            (SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file"),
        ],
        initial=SOURCE_MODE_RECORDED_ARTIFACT,
        widget=forms.RadioSelect,
        help_text=(
            "Use a recorded local artifact already present on disk, or upload a "
            "backup file that must resolve to one trusted authoritative artifact "
            "recorded on the snapshot seam."
        ),
    )

    artifact_id = forms.IntegerField(
        label="Eligible local artifact",
        min_value=1,
        required=False,
        widget=forms.Select(),
        help_text=(
            "Choose a row-backed PostgreSQL dump artifact whose local file is "
            "already present on disk."
        ),
    )
    uploaded_file = forms.FileField(
        label="Uploaded backup file",
        required=False,
        help_text=(
            "Upload a PostgreSQL custom dump to quarantine staging. The upload is "
            "accepted only when its checksum and size resolve to exactly one "
            "trusted authoritative artifact with a complete snapshot contract."
        ),
    )
    confirmation = forms.CharField(
        label="Exact artifact filename",
        strip=False,
        help_text=(
            "Type the exact authoritative artifact filename before dry-run "
            "validation or restore can continue. Uploaded files must still match "
            "the recorded artifact filename exactly here."
        ),
    )

    def __init__(
        self,
        *args: Any,
        artifact_choices: list[tuple[int, str]],
        allow_recorded_artifact_source: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.allow_recorded_artifact_source = allow_recorded_artifact_source
        if allow_recorded_artifact_source:
            self.fields["source_mode"].choices = [
                (
                    self.SOURCE_MODE_RECORDED_ARTIFACT,
                    "Recorded local artifact",
                ),
                (self.SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file"),
            ]
            self.fields["source_mode"].initial = self.SOURCE_MODE_RECORDED_ARTIFACT
        else:
            self.fields["source_mode"].choices = [
                (self.SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file")
            ]
            self.fields["source_mode"].initial = self.SOURCE_MODE_UPLOADED_FILE
            self.fields["source_mode"].error_messages["invalid_choice"] = (
                "Recorded local artifacts are unavailable for your current permissions."
            )
            self.fields["source_mode"].help_text = (
                "Uploaded backup file is the only restore source available for "
                "your current permissions."
            )
        self.fields["artifact_id"].widget.choices = [
            ("", "Select an eligible local backup artifact"),
            *artifact_choices,
        ]

    def clean(self) -> dict[str, Any]:
        """Require the source-specific restore input before continuing."""
        cleaned_data: dict[str, Any] = super().clean() or {}
        default_source_mode = (
            self.SOURCE_MODE_RECORDED_ARTIFACT
            if self.allow_recorded_artifact_source
            else self.SOURCE_MODE_UPLOADED_FILE
        )
        source_mode = cleaned_data.get("source_mode") or default_source_mode
        cleaned_data["source_mode"] = source_mode

        if self.has_error("source_mode"):
            return cleaned_data

        if source_mode == self.SOURCE_MODE_RECORDED_ARTIFACT:
            if not self.allow_recorded_artifact_source:
                self.add_error(
                    "source_mode",
                    "Recorded local artifacts are unavailable for your current permissions.",
                )
                return cleaned_data
            if cleaned_data.get("artifact_id") is None:
                self.add_error(
                    "artifact_id",
                    "Choose an eligible local backup artifact before continuing.",
                )
        elif source_mode == self.SOURCE_MODE_UPLOADED_FILE:
            if cleaned_data.get("uploaded_file") is None:
                self.add_error(
                    "uploaded_file",
                    "Upload a backup file before continuing.",
                )
        else:
            self.add_error("source_mode", "Choose a restore source before continuing.")

        return cleaned_data


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

    def _get_artifact_admin(self) -> BackupArtifactAdmin | None:
        """Return the registered BackupArtifact admin when available."""
        artifact_admin = self.admin_site._registry.get(BackupArtifact)
        if isinstance(artifact_admin, BackupArtifactAdmin):
            return artifact_admin
        return None

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
        """Render and execute the guarded admin restore workflow."""
        if request.method == "POST":
            if not self.has_change_permission(request):
                raise PermissionDenied
        elif not self.has_view_or_change_permission(request):
            raise PermissionDenied

        policy = ensure_default_policy()
        can_view_restore_artifacts = self._can_view_restore_artifacts(request)
        eligible_artifacts = (
            self._get_admin_restore_candidates() if can_view_restore_artifacts else []
        )
        form = BackupPolicyRestoreForm(
            artifact_choices=self._build_restore_artifact_choices(eligible_artifacts),
            allow_recorded_artifact_source=can_view_restore_artifacts,
        )
        selected_artifact: BackupArtifact | None = None

        if request.method == "POST":
            form = BackupPolicyRestoreForm(
                request.POST,
                request.FILES,
                artifact_choices=self._build_restore_artifact_choices(
                    eligible_artifacts
                ),
                allow_recorded_artifact_source=can_view_restore_artifacts,
            )
            operation = request.POST.get("operation")
            if operation not in {"dry_run", "restore"}:
                form.add_error(
                    None,
                    "Choose either dry-run validation or restore before continuing.",
                )

            if form.is_valid() and operation is not None:
                source_mode = form.cleaned_data["source_mode"]
                if source_mode == BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT:
                    if not can_view_restore_artifacts:
                        form.add_error(
                            "source_mode",
                            "Recorded local artifacts are unavailable for your current permissions.",
                        )
                    else:
                        artifact_id = form.cleaned_data["artifact_id"]
                        selected_artifact = self._get_restore_artifact_by_id(
                            artifact_id
                        )

                        if artifact_id is not None and selected_artifact is None:
                            form.add_error(
                                "artifact_id",
                                "The selected backup artifact no longer exists.",
                            )
                        elif selected_artifact is not None:
                            ineligible_reason = (
                                self._get_admin_restore_ineligible_reason(
                                    selected_artifact
                                )
                            )
                            if ineligible_reason is not None:
                                form.add_error("artifact_id", ineligible_reason)
                        elif not eligible_artifacts:
                            form.add_error(
                                None,
                                "No eligible local backup artifacts are currently available for admin restore.",
                            )

                if not form.errors:
                    if operation == "dry_run":
                        try:
                            if (
                                form.cleaned_data["source_mode"]
                                == BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT
                            ):
                                assert selected_artifact is not None
                                result = restore_backup_artifact(
                                    selected_artifact,
                                    confirmation=form.cleaned_data["confirmation"],
                                    dry_run=True,
                                    resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
                                )
                            else:
                                result = restore_admin_uploaded_backup(
                                    form.cleaned_data["uploaded_file"],
                                    confirmation=form.cleaned_data["confirmation"],
                                    dry_run=True,
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

                            redirect_url = reverse(
                                "admin:quickscale_modules_backups_backuppolicy_restore"
                            )
                            if selected_artifact is not None:
                                redirect_url = (
                                    f"{redirect_url}?artifact_id={selected_artifact.pk}"
                                )
                            return HttpResponseRedirect(redirect_url)

                    # SA20: Async dispatch for actual restore — return immediately,
                    # let the management command handle execution in background.
                    # Guard against dry_run fallthrough when the dry run
                    # raises and adds a form error.
                    elif operation == "restore":
                        try:
                            if (
                                form.cleaned_data["source_mode"]
                                == BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT
                            ):
                                assert selected_artifact is not None
                                confirm_value = form.cleaned_data["confirmation"]
                                manage_py = _get_manage_py()

                                # CR-SA20-007: Persist STATUS_RESTORING before
                                # Popen so a fast child terminal update is never
                                # missed or overwritten.  Roll back to the
                                # pre-spawn status/metadata on spawn failure so a
                                # retried FAILED/RESTORED artifact does not lose
                                # its prior restore_started_at and restore_error.
                                # CR-SA20-REV-002: Use atomic compare-and-swap
                                # so concurrent submissions do not both dispatch
                                # Popen for the same artifact.
                                pre_spawn_status = selected_artifact.status
                                pre_spawn_restore_started_at = (
                                    selected_artifact.restore_started_at
                                )
                                pre_spawn_restore_error = (
                                    selected_artifact.restore_error
                                )
                                if not _atomic_claim_restore(selected_artifact):
                                    ineligible_reason = (
                                        self._get_admin_restore_ineligible_reason(
                                            selected_artifact
                                        )
                                    )
                                    if ineligible_reason is not None:
                                        raise BackupRestoreBlocked(ineligible_reason)
                                    raise BackupRestoreBlocked(
                                        "This backup artifact is currently being "
                                        "restored. Wait for the restore to "
                                        "complete before retrying."
                                    )
                                try:
                                    subprocess.Popen(
                                        [
                                            sys.executable,
                                            manage_py,
                                            "backups_restore",
                                            str(selected_artifact.pk),
                                            "--confirm",
                                            confirm_value,
                                            "--local-only",
                                        ],
                                        close_fds=True,
                                    )
                                except Exception:
                                    # Rollback: restore pre-spawn status/metadata
                                    # so a spawn failure never strands the artifact
                                    # in STATUS_RESTORING or loses prior failure
                                    # metadata on retry.
                                    selected_artifact.status = pre_spawn_status
                                    selected_artifact.restore_started_at = (
                                        pre_spawn_restore_started_at
                                    )
                                    selected_artifact.restore_error = (
                                        pre_spawn_restore_error
                                    )
                                    selected_artifact.save(
                                        update_fields=[
                                            "status",
                                            "restore_started_at",
                                            "restore_error",
                                            "updated_at",
                                        ]
                                    )
                                    raise
                            else:
                                # SA20 uploaded-file restore: route through
                                # the trusted authoritative seam before
                                # dispatching the background restore.  Uses
                                # the same staging + trusted resolver as
                                # restore_admin_uploaded_backup (sync flow)
                                # so that ambiguous, incomplete-snapshot,
                                # and untrusted cases are rejected
                                # identically.
                                uploaded_file = form.cleaned_data["uploaded_file"]
                                staging_directory = Path(
                                    mkdtemp(prefix=("quickscale-backups-admin-upload-"))
                                )
                                try:
                                    staged_upload = _stage_admin_restore_upload(
                                        uploaded_file,
                                        staging_directory=(staging_directory),
                                    )
                                    trusted_artifact = (
                                        _resolve_admin_uploaded_restore_artifact(
                                            checksum_sha256=(
                                                staged_upload.checksum_sha256
                                            ),
                                            size_bytes=(staged_upload.size_bytes),
                                        )
                                    )
                                except Exception:
                                    _cleanup_admin_restore_upload_directory(
                                        staging_directory
                                    )
                                    raise

                                # CR-SA20-REV-001: Reject already-restoring
                                # artifacts with parity to the recorded-artifact
                                # branch.  The resolver above does not check
                                # STATUS_RESTORING (its trust model mirrors
                                # the sync path), so we guard here before
                                # copy or Popen.  CR-SA20-REV-002's atomic
                                # compare-and-swap below is the real race-proof
                                # gate; this early check is an optimization to
                                # avoid unnecessary work on a clearly-stale
                                # artifact.
                                if (
                                    trusted_artifact.status
                                    == BackupArtifact.STATUS_RESTORING
                                ):
                                    _cleanup_admin_restore_upload_directory(
                                        staging_directory
                                    )
                                    raise BackupRestoreBlocked(
                                        "This backup artifact is currently being "
                                        "restored. Wait for the restore to "
                                        "complete before retrying."
                                    )

                                confirm_value = form.cleaned_data["confirmation"]
                                if confirm_value.strip() != trusted_artifact.filename:
                                    _cleanup_admin_restore_upload_directory(
                                        staging_directory
                                    )
                                    raise BackupRestoreBlocked(
                                        "Confirmation must exactly match "
                                        "the backup filename."
                                    )

                                # CR-SA20-005: Always remap to a trusted
                                # path under get_local_backup_directory().
                                # Ignore any unsafe persisted local_path
                                # — persist only after a successful copy.
                                policy_snapshot = load_policy_snapshot()
                                local_dir = get_local_backup_directory(policy_snapshot)
                                local_dir.mkdir(parents=True, exist_ok=True)
                                local_path = local_dir / trusted_artifact.filename

                                # Skip the copy when the staged upload is already at the
                                # artifact's expected local path (same file from
                                # testing or inline materialization).  Use
                                # resolve() to handle symlinks and relative
                                # vs absolute path normalization.
                                if (
                                    staged_upload.local_path.resolve()
                                    != local_path.resolve()
                                ):
                                    # CR-SA20-005: Remove any pre-existing
                                    # destination (including symlinks) before
                                    # copy so we always materialize a regular
                                    # file inside the authoritative backup
                                    # root.
                                    local_path.unlink(missing_ok=True)
                                    shutil.copy2(
                                        staged_upload.local_path,
                                        local_path,
                                    )
                                _cleanup_admin_restore_upload_directory(
                                    staging_directory
                                )

                                # Persist local_path only after successful
                                # copy so a failed copy does not leave a
                                # dangling path on the artifact.
                                trusted_artifact.local_path = str(local_path)
                                trusted_artifact.save(
                                    update_fields=[
                                        "local_path",
                                        "updated_at",
                                    ]
                                )

                                # Dispatch async via artifact-id path.
                                # CR-SA20-006: Always pass --local-only so
                                # the child never remote-materializes.
                                # CR-SA20-007: Persist STATUS_RESTORING before
                                # Popen so a fast child terminal update is never
                                # missed or overwritten.  Roll back to the
                                # pre-spawn status/metadata on spawn failure so a
                                # retried FAILED/RESTORED artifact does not lose
                                # its prior restore_started_at and restore_error.
                                # CR-SA20-REV-002: Use atomic compare-and-swap
                                # so concurrent submissions do not both dispatch
                                # Popen for the same artifact.
                                manage_py = _get_manage_py()
                                pre_spawn_status = trusted_artifact.status
                                pre_spawn_restore_started_at = (
                                    trusted_artifact.restore_started_at
                                )
                                pre_spawn_restore_error = trusted_artifact.restore_error
                                if not _atomic_claim_restore(trusted_artifact):
                                    if (
                                        trusted_artifact.status
                                        == BackupArtifact.STATUS_DELETED
                                    ):
                                        raise BackupRestoreBlocked(
                                            "Deleted backup artifacts cannot be "
                                            "restored from admin."
                                        )
                                    raise BackupRestoreBlocked(
                                        "This backup artifact is currently being "
                                        "restored. Wait for the restore to "
                                        "complete before retrying."
                                    )
                                try:
                                    subprocess.Popen(
                                        [
                                            sys.executable,
                                            manage_py,
                                            "backups_restore",
                                            str(trusted_artifact.pk),
                                            "--confirm",
                                            confirm_value,
                                            "--local-only",
                                        ],
                                        close_fds=True,
                                    )
                                except Exception:
                                    # Rollback: restore pre-spawn status/metadata
                                    # so a spawn failure never strands the artifact
                                    # in STATUS_RESTORING or loses prior failure
                                    # metadata on retry.
                                    trusted_artifact.status = pre_spawn_status
                                    trusted_artifact.restore_started_at = (
                                        pre_spawn_restore_started_at
                                    )
                                    trusted_artifact.restore_error = (
                                        pre_spawn_restore_error
                                    )
                                    trusted_artifact.save(
                                        update_fields=[
                                            "status",
                                            "restore_started_at",
                                            "restore_error",
                                            "updated_at",
                                        ]
                                    )
                                    raise
                        except Exception as exc:
                            form.add_error(
                                None,
                                f"Failed to initiate background restore: {exc}",
                            )
                        else:
                            self.message_user(
                                request,
                                "Restore has been initiated in the background. "
                                "Check the artifact's status for progress or errors.",
                                level=messages.SUCCESS,
                            )
                            return HttpResponseRedirect(
                                reverse(
                                    "admin:quickscale_modules_backups_backuppolicy_changelist"
                                )
                            )
        else:
            if can_view_restore_artifacts:
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
                    allow_recorded_artifact_source=can_view_restore_artifacts,
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
        if artifact.status == BackupArtifact.STATUS_DELETED:
            return "Deleted backup artifacts cannot be restored from admin."
        if artifact.status == BackupArtifact.STATUS_RESTORING:
            return (
                "This backup artifact is currently being restored. "
                "Wait for the restore to complete before retrying."
            )
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
        except TypeError:
            return None
        except ValueError:
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
    actions = ["validate_selected_backups"]
    change_list_template = (
        "admin/quickscale_modules_backups/backupartifact/change_list.html"
    )

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
                name="quickscale_modules_backups_backupartifact_create",
            ),
            path(
                "<int:artifact_id>/download/",
                self.admin_site.admin_view(self.download_view),
                name="quickscale_modules_backups_backupartifact_download",
            ),
        ]
        return custom_urls + urls

    def _get_policy_admin(self) -> BackupPolicyAdmin | None:
        """Return the registered BackupPolicy admin when available."""
        policy_admin = self.admin_site._registry.get(BackupPolicy)
        if isinstance(policy_admin, BackupPolicyAdmin):
            return policy_admin
        return None

    def _has_policy_change_permission(self, request: HttpRequest) -> bool:
        """Mirror the existing BackupPolicy change gate for backup creation."""
        policy_admin = self._get_policy_admin()
        if policy_admin is None:
            return False
        return policy_admin.has_change_permission(request)

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
            return obj.authoritative_snapshot
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
            return snapshot.snapshot_id

        snapshot_id = str(self._snapshot_metadata(obj).get("snapshot_id", "")).strip()
        return snapshot_id or None

    def _snapshot_status_value(self, obj: BackupArtifact) -> str | None:
        """Return the tracked snapshot lifecycle status when one is available."""
        snapshot = self._get_snapshot(obj)
        if snapshot is not None:
            return snapshot.status

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
                reverse("admin:quickscale_modules_backups_backupartifact_changelist")
            )

        policy_admin = self._get_policy_admin()
        if policy_admin is None:
            raise PermissionDenied

        policy_admin.create_backup_now(request, BackupPolicy.objects.none())
        return HttpResponseRedirect(
            reverse("admin:quickscale_modules_backups_backupartifact_changelist")
        )

    def _has_downloadable_local_file(self, obj: BackupArtifact) -> bool:
        """Return whether the admin can still offer a local download action."""
        if obj.status == BackupArtifact.STATUS_DELETED:
            return False

        try:
            download_backup_path(obj)
        except BackupError:
            return False
        return True

    @admin.display(description="Classification")
    def restore_scope_badge(self, obj: BackupArtifact) -> str:
        return obj.effective_restore_scope() or "unclassified"

    @admin.display(description="Snapshot status")
    def snapshot_status_badge(self, obj: BackupArtifact) -> str:
        snapshot_status = self._snapshot_status_value(obj)
        if snapshot_status is None:
            return "Untracked"

        return dict(BackupSnapshot.STATUS_CHOICES).get(snapshot_status, snapshot_status)

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
            "admin:quickscale_modules_backups_backupartifact_download",
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
