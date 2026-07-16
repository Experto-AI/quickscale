"""Initial migration for the QuickScale Orgs module.

Collapsed SA90-MSQ migration: final-schema 0001 with Organization,
OrganizationMembership, OrganizationInvitation, and OrganizationTombstone
models.  Includes is_system field and unique_system_org constraint.

The orgs module is the control-plane for tenancy — its own models are
EXCLUDED_REVIEWED in the tenant-table registry, and it runs before any
enrolled tables exist, so a FORCE RLS policy refresh here would be a
guaranteed no-op and is therefore removed.  Each tenant module's own
0001 migration remains authoritative for RLS installation on its own
tables.
"""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
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
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=150, unique=True)),
                ("stripe_customer_id", models.CharField(blank=True, max_length=255)),
                ("is_personal", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "is_system",
                    models.BooleanField(default=False),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="OrganizationInvitation",
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
                ("email", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("viewer", "Viewer"),
                            ("member", "Member"),
                            ("admin", "Admin"),
                            ("owner", "Owner"),
                        ],
                        default="member",
                        max_length=20,
                    ),
                ),
                (
                    "token",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_organization_invitations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["email"],
            },
        ),
        migrations.CreateModel(
            name="OrganizationMembership",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("viewer", "Viewer"),
                            ("member", "Member"),
                            ("admin", "Admin"),
                            ("owner", "Owner"),
                        ],
                        default="member",
                        max_length=20,
                    ),
                ),
                (
                    "joined_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invited_organization_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organization_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["organization_id", "user_id"],
                "unique_together": {("user", "organization")},
            },
        ),
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
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_system", True)),
                fields=("is_system",),
                name="unique_system_org",
            ),
        ),
    ]
