from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "quickscale_modules_backups",
            "0003_backupartifact_restore_scope_and_versions",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="BackupSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "snapshot_id",
                    models.CharField(editable=False, max_length=64, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                            ("deleted", "Deleted"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "source_environment",
                    models.CharField(default="local", max_length=64),
                ),
                ("local_root_path", models.CharField(max_length=512)),
                ("remote_root_key", models.CharField(blank=True, max_length=512)),
                (
                    "child_descriptors_json",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "rollback_pin_expires_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "rollback_pin_reason",
                    models.CharField(blank=True, max_length=255),
                ),
                ("failure_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "authoritative_dump",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="authoritative_snapshot",
                        to="quickscale_modules_backups.backupartifact",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backup snapshot",
                "verbose_name_plural": "Backup snapshots",
                "db_table": "quickscale_modules_backups_snapshot",
                "ordering": ["-created_at"],
            },
        ),
    ]
