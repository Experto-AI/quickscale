"""Data models for QuickScale backups."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


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
    database_engine = models.CharField(max_length=255)
    database_name = models.CharField(max_length=255, blank=True)
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

    def download_path(self) -> str:
        """Return the best available operator-facing download path."""
        if self.local_path:
            return self.local_path
        return self.remote_key

    def is_local_available(self) -> bool:
        """Return whether a local artifact path is currently recorded."""
        return bool(self.local_path)
