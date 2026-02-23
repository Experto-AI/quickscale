"""Initial migration for QuickScale Forms module"""

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
            name="Form",
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
                ("slug", models.SlugField(unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "success_message",
                    models.TextField(default="Thank you, we'll be in touch."),
                ),
                ("redirect_url", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("spam_protection_enabled", models.BooleanField(default=True)),
                (
                    "notify_emails",
                    models.TextField(
                        blank=True,
                        help_text="Comma-separated email addresses to notify on every submission.",
                    ),
                ),
                (
                    "data_retention_days",
                    models.PositiveIntegerField(
                        default=365,
                        help_text="Submissions older than this many days are eligible for anonymization.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_forms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_form",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="FormField",
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
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("email", "Email"),
                            ("textarea", "Textarea"),
                            ("select", "Select"),
                            ("checkbox", "Checkbox"),
                            ("radio", "Radio"),
                            ("number", "Number"),
                            ("url", "URL"),
                            ("tel", "Telephone"),
                            ("date", "Date"),
                            ("hidden", "Hidden"),
                        ],
                        max_length=20,
                    ),
                ),
                ("label", models.CharField(max_length=200)),
                ("name", models.SlugField(max_length=100)),
                ("placeholder", models.CharField(blank=True, max_length=200)),
                ("help_text", models.CharField(blank=True, max_length=500)),
                ("required", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField()),
                ("options", models.JSONField(blank=True, default=list)),
                ("validation_rules", models.JSONField(blank=True, default=dict)),
                (
                    "layout_hint",
                    models.CharField(
                        choices=[
                            ("full", "Full width"),
                            ("half_left", "Half width (left)"),
                            ("half_right", "Half width (right)"),
                        ],
                        default="full",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "form",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="quickscale_modules_forms.form",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formfield",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="FormSubmission",
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
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("is_spam", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("read", "Read"),
                            ("replied", "Replied"),
                            ("archived", "Archived"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "form",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="submissions",
                        to="quickscale_modules_forms.form",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formsubmission",
                "ordering": ["-submitted_at"],
            },
        ),
        migrations.CreateModel(
            name="FormFieldValue",
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
                ("field_name", models.CharField(max_length=100)),
                ("field_label", models.CharField(max_length=200)),
                ("value", models.TextField()),
                (
                    "field",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="values",
                        to="quickscale_modules_forms.formfield",
                    ),
                ),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="values",
                        to="quickscale_modules_forms.formsubmission",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formfieldvalue",
            },
        ),
        migrations.AlterUniqueTogether(
            name="formfield",
            unique_together={("form", "name")},
        ),
    ]
