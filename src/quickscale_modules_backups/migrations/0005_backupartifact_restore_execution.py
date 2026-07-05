"""Add STATUS_RESTORING, restore_started_at, and restore_error to BackupArtifact (SA20)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "quickscale_modules_backups",
            "0004_backupsnapshot_snapshot_substrate",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="backupartifact",
            name="restore_started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the most recent background restore was initiated.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="backupartifact",
            name="restore_error",
            field=models.TextField(
                blank=True,
                help_text="Error message from a failed background restore, if any.",
            ),
        ),
        migrations.AlterField(
            model_name="backupartifact",
            name="status",
            field=models.CharField(
                choices=[
                    ("ready", "Ready"),
                    ("validated", "Validated"),
                    ("restoring", "Restoring..."),
                    ("failed", "Failed"),
                    ("deleted", "Deleted"),
                    ("restored", "Restored"),
                ],
                default="ready",
                max_length=20,
            ),
        ),
    ]
