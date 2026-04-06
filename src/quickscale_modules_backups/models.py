"""Data models for QuickScale backups."""

from datetime import datetime

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone as django_timezone


class BackupPolicy(models.Model):
    """Operational policy controlling how backup artifacts are created and retained."""

    TARGET_MODE_LOCAL = "local"
    TARGET_MODE_PRIVATE_REMOTE = "private_remote"
    TARGET_MODE_CHOICES = [
        (TARGET_MODE_LOCAL, "Local private storage"),
        (TARGET_MODE_PRIVATE_REMOTE, "Private remote offload"),
    ]

    key = models.CharField(
        max_length=32, unique=True, default="default", editable=False
    )
    retention_days = models.PositiveIntegerField(
        default=14,
        validators=[MinValueValidator(1)],
        help_text="Backup artifacts older than this many days are pruned.",
    )
    naming_prefix = models.CharField(
        max_length=64,
        default="db",
        help_text="Prefix used when generating backup artifact filenames.",
    )
    target_mode = models.CharField(
        max_length=20,
        choices=TARGET_MODE_CHOICES,
        default=TARGET_MODE_LOCAL,
        help_text="Backups remain private regardless of target mode.",
    )
    local_directory = models.CharField(
        max_length=255,
        default=".quickscale/backups",
        help_text="Private local directory for stored backup artifacts.",
    )
    remote_bucket_name = models.CharField(max_length=255, blank=True)
    remote_prefix = models.CharField(
        max_length=255, blank=True, default="backups/private"
    )
    remote_endpoint_url = models.CharField(max_length=255, blank=True)
    remote_region_name = models.CharField(max_length=64, blank=True)
    remote_access_key_id_env_var = models.CharField(max_length=255, blank=True)
    remote_secret_access_key_env_var = models.CharField(max_length=255, blank=True)
    automation_enabled = models.BooleanField(
        default=False,
        help_text="Metadata only. Scheduled execution remains command-driven.",
    )
    schedule = models.CharField(
        max_length=100,
        default="0 2 * * *",
        blank=True,
        help_text="Cron-like schedule documentation for external schedulers.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_backups"
        db_table = "quickscale_modules_backups_policy"
        verbose_name = "Backup policy"
        verbose_name_plural = "Backup policies"

    def __str__(self) -> str:
        return f"Backup policy ({self.target_mode})"


class BackupArtifact(models.Model):
    """Recorded metadata for a created backup artifact."""

    STATUS_READY = "ready"
    STATUS_VALIDATED = "validated"
    STATUS_FAILED = "failed"
    STATUS_DELETED = "deleted"
    STATUS_RESTORED = "restored"
    STATUS_CHOICES = [
        (STATUS_READY, "Ready"),
        (STATUS_VALIDATED, "Validated"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DELETED, "Deleted"),
        (STATUS_RESTORED, "Restored"),
    ]

    STORAGE_TARGET_LOCAL = "local"
    STORAGE_TARGET_PRIVATE_REMOTE = "private_remote"
    STORAGE_TARGET_CHOICES = [
        (STORAGE_TARGET_LOCAL, "Local private storage"),
        (STORAGE_TARGET_PRIVATE_REMOTE, "Private remote offload"),
    ]

    RESTORE_SCOPE_EXPORT_ONLY = "export_only"
    RESTORE_SCOPE_LOCAL_ONLY = "local_only"
    RESTORE_SCOPE_PORTABLE = "portable"
    RESTORE_SCOPE_CHOICES = [
        (RESTORE_SCOPE_EXPORT_ONLY, "Export only"),
        (RESTORE_SCOPE_LOCAL_ONLY, "Local restore only"),
        (RESTORE_SCOPE_PORTABLE, "Portable restore"),
    ]

    filename = models.CharField(max_length=255, unique=True)
    storage_target = models.CharField(
        max_length=20,
        choices=STORAGE_TARGET_CHOICES,
        default=STORAGE_TARGET_LOCAL,
    )
    local_path = models.CharField(max_length=512, blank=True)
    remote_key = models.CharField(max_length=512, blank=True)
    remote_bucket_name = models.CharField(max_length=255, blank=True)
    remote_endpoint_url = models.CharField(max_length=255, blank=True)
    remote_region_name = models.CharField(max_length=64, blank=True)
    checksum_sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField(default=0)
    backup_format = models.CharField(max_length=32, default="json")
    restore_scope = models.CharField(
        max_length=20,
        choices=RESTORE_SCOPE_CHOICES,
        null=True,
        blank=True,
        help_text=(
            "Conservative restore classification: export_only, local_only, or portable."
        ),
    )
    database_engine = models.CharField(max_length=255)
    database_name = models.CharField(max_length=255, blank=True)
    database_server_major = models.PositiveIntegerField(null=True, blank=True)
    dump_client_major = models.PositiveIntegerField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_READY
    )
    trigger = models.CharField(max_length=32, default="manual")
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quickscale_backup_artifacts",
    )
    validation_notes = models.TextField(blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_backups"
        db_table = "quickscale_modules_backups_artifact"
        ordering = ["-created_at"]
        verbose_name = "Backup artifact"
        verbose_name_plural = "Backup artifacts"

    def __str__(self) -> str:
        return self.filename

    def effective_restore_scope(self) -> str | None:
        """Return the recorded restore scope or a conservative legacy fallback."""
        if self.restore_scope:
            return self.restore_scope
        if self.backup_format == "json":
            return self.RESTORE_SCOPE_EXPORT_ONLY
        if self.backup_format == "pg_dump_custom":
            return self.RESTORE_SCOPE_LOCAL_ONLY
        return None

    def restore_scope_label(self) -> str:
        """Return a human-readable classification label."""
        restore_scope = self.effective_restore_scope()
        if restore_scope is None:
            return "Unclassified"
        return dict(self.RESTORE_SCOPE_CHOICES).get(restore_scope, "Unclassified")

    def is_export_only(self) -> bool:
        """Return whether the artifact is classified as export-only."""
        return self.effective_restore_scope() == self.RESTORE_SCOPE_EXPORT_ONLY

    def is_local_only(self) -> bool:
        """Return whether the artifact is classified as local-only."""
        return self.effective_restore_scope() == self.RESTORE_SCOPE_LOCAL_ONLY

    def is_portable(self) -> bool:
        """Return whether the artifact is classified as portable."""
        return self.effective_restore_scope() == self.RESTORE_SCOPE_PORTABLE

    def download_path(self) -> str:
        """Return the best available operator-facing download path."""
        if self.local_path:
            return self.local_path
        return self.remote_key

    def is_local_available(self) -> bool:
        """Return whether a local artifact path is currently recorded."""
        return bool(self.local_path)


class BackupSnapshot(models.Model):
    """Internal snapshot substrate that tracks dump artifacts plus private sidecars."""

    STATUS_PENDING = "pending"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DELETED, "Deleted"),
    ]

    snapshot_id = models.CharField(max_length=64, unique=True, editable=False)
    authoritative_dump = models.OneToOneField(
        BackupArtifact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="authoritative_snapshot",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    source_environment = models.CharField(max_length=64, default="local")
    local_root_path = models.CharField(max_length=512)
    remote_root_key = models.CharField(max_length=512, blank=True)
    child_descriptors_json = models.JSONField(default=dict, blank=True)
    rollback_pin_expires_at = models.DateTimeField(null=True, blank=True)
    rollback_pin_reason = models.CharField(max_length=255, blank=True)
    failure_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_backups"
        db_table = "quickscale_modules_backups_snapshot"
        ordering = ["-created_at"]
        verbose_name = "Backup snapshot"
        verbose_name_plural = "Backup snapshots"

    def __str__(self) -> str:
        return self.snapshot_id

    def save(self, *args: object, **kwargs: object) -> None:
        """Prevent snapshot identifiers from being reassigned after creation."""
        if self.pk is not None:
            original_snapshot_id = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list(
                    "snapshot_id",
                    flat=True,
                )
                .first()
            )
            if (
                original_snapshot_id is not None
                and original_snapshot_id != self.snapshot_id
            ):
                raise ValueError("snapshot_id is immutable")
        super().save(*args, **kwargs)

    def has_active_rollback_pin(self, *, now: datetime | None = None) -> bool:
        """Return whether this snapshot is protected from pruning right now."""
        if self.rollback_pin_expires_at is None:
            return False

        comparison_time = now or django_timezone.now()
        return self.rollback_pin_expires_at > comparison_time
