"""Create OrganizationTombstone model for purge rerun semantics (T1.17)."""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    """Create the OrganizationTombstone table."""

    dependencies = [
        ("quickscale_modules_orgs", "0003_alter_organization_is_system"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationTombstone",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "organization_id",
                    models.UUIDField(
                        unique=True,
                        verbose_name="purged organization UUID",
                        help_text="The UUID of the purged organization (not a FK — the org row is gone).",
                    ),
                ),
                (
                    "purged_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "purged_by_user_id",
                    models.CharField(
                        max_length=255,
                        blank=True,
                        default="",
                        verbose_name="purged by user ID",
                        help_text="Operator identifier who triggered the purge, if known.",
                    ),
                ),
                (
                    "reason",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Optional human-readable reason for the purge.",
                    ),
                ),
            ],
            options={
                "verbose_name": "organization tombstone",
                "verbose_name_plural": "organization tombstones",
                "ordering": ["-purged_at"],
            },
        ),
    ]
