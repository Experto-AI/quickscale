"""Initial migration for CRM module with default pipeline stages"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_default_stages(apps, schema_editor):
    """Create default pipeline stages"""
    Stage = apps.get_model("quickscale_modules_crm", "Stage")
    stages = [
        {"name": "Prospecting", "order": 1},
        {"name": "Negotiation", "order": 2},
        {"name": "Closed-Won", "order": 3},
        {"name": "Closed-Lost", "order": 4},
    ]
    for stage_data in stages:
        Stage.objects.create(**stage_data)


def reverse_default_stages(apps, schema_editor):
    """Remove default pipeline stages"""
    Stage = apps.get_model("quickscale_modules_crm", "Stage")
    Stage.objects.filter(
        name__in=["Prospecting", "Negotiation", "Closed-Won", "Closed-Lost"]
    ).delete()


class Migration(migrations.Migration):
    """Initial migration for CRM module"""

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Tag model
        migrations.CreateModel(
            name="Tag",
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
                ("name", models.CharField(max_length=50, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        # Company model
        migrations.CreateModel(
            name="Company",
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
                ("name", models.CharField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("website", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "Companies",
                "ordering": ["name"],
            },
        ),
        # Stage model
        migrations.CreateModel(
            name="Stage",
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
                ("name", models.CharField(max_length=100)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "name"],
            },
        ),
        # Contact model
        migrations.CreateModel(
            name="Contact",
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
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20)),
                (
                    "title",
                    models.CharField(blank=True, help_text="Job title", max_length=100),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("in_discussion", "In Discussion"),
                            ("pending_response", "Pending Response"),
                            ("inactive", "Inactive"),
                        ],
                        default="new",
                        max_length=50,
                    ),
                ),
                (
                    "last_contacted_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Automatically updated when a note is logged",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="quickscale_modules_crm.company",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="contacts",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
            },
        ),
        # Deal model
        migrations.CreateModel(
            name="Deal",
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
                ("title", models.CharField(max_length=200)),
                (
                    "amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Deal value in USD",
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("expected_close_date", models.DateField(blank=True, null=True)),
                (
                    "probability",
                    models.IntegerField(
                        default=50, help_text="Forecast likelihood (0-100%)"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deals",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_deals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="deals",
                        to="quickscale_modules_crm.stage",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="deals",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        # ContactNote model
        migrations.CreateModel(
            name="ContactNote",
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
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        # DealNote model
        migrations.CreateModel(
            name="DealNote",
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
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "deal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.deal",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        # Create default pipeline stages
        migrations.RunPython(create_default_stages, reverse_default_stages),
    ]
