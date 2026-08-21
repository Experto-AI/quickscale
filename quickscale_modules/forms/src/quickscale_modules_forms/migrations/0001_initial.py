"""Initial Forms schema with tenant composite-FK, RLS, and seed contracts."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
import quickscale_modules_forms.models
from django.conf import settings
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    apply_force_rls,
    remove_composite_child_fk,
    revert_force_rls,
)

FORMS_FORM_TABLE = "quickscale_modules_forms_form"
FORMS_FORMFIELD_TABLE = "quickscale_modules_forms_formfield"
FORMS_FORMSUBMISSION_TABLE = "quickscale_modules_forms_formsubmission"
FORMS_FORMFIELDVALUE_TABLE = "quickscale_modules_forms_formfieldvalue"
FORMS_FORM_RLS_POLICY = "forms_form_org_isolation"
FORMS_FORMFIELD_RLS_POLICY = "forms_formfield_org_isolation"
FORMS_FORMSUBMISSION_RLS_POLICY = "forms_formsubmission_org_isolation"
FORMS_FORMFIELDVALUE_RLS_POLICY = "forms_formfieldvalue_org_isolation"
_FORMS_ALL_RLS_TARGETS = (
    (FORMS_FORM_TABLE, FORMS_FORM_RLS_POLICY),
    (FORMS_FORMFIELD_TABLE, FORMS_FORMFIELD_RLS_POLICY),
    (FORMS_FORMSUBMISSION_TABLE, FORMS_FORMSUBMISSION_RLS_POLICY),
    (FORMS_FORMFIELDVALUE_TABLE, FORMS_FORMFIELDVALUE_RLS_POLICY),
)
FORMS_FORM_ID_ORG_UNIQUE = "forms_form_id_org_unique"
FORMS_FORMFIELD_ID_ORG_UNIQUE = "forms_formfield_id_org_unique"
FORMS_FORMSUBMISSION_ID_ORG_UNIQUE = "forms_formsubmission_id_org_unique"
FORMS_FORMFIELD_FORM_ORG_FK = "forms_formfield_form_org_fk"
FORMS_FORMSUBMISSION_FORM_ORG_FK = "forms_formsubmission_form_org_fk"
FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK = "forms_formfieldvalue_submission_org_fk"
FORMS_FORMFIELDVALUE_FIELD_ORG_FK = "forms_formfieldvalue_field_org_fk"

_RATING_OPTIONS = [
    {"value": str(i), "label": label}
    for i, label in enumerate(
        ("1 — Poor", "2 — Fair", "3 — Good", "4 — Very Good", "5 — Excellent"),
        1,
    )
]
_PRIORITY_OPTIONS = [
    {"value": value, "label": label}
    for value, label in (("low", "Low"), ("medium", "Medium"), ("high", "High"))
]


def _preset(
    title: str,
    slug: str,
    description: str,
    success_message: str,
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "title": title,
        "slug": slug,
        "description": description,
        "success_message": success_message,
        "notify_emails": "",
        "fields": fields,
    }


def _preset_field(
    name: str,
    field_type: str,
    label: str,
    required: bool,
    order: int,
    layout_hint: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "field_type": field_type,
        "label": label,
        "required": required,
        "order": order,
        "layout_hint": layout_hint,
        **kwargs,
    }


_PRESETS = [
    _preset(
        "Contact",
        "contact",
        "Get in Touch — share your current constraints, timeline, and target outcomes.",
        "Thank you, we will respond within 24 hours.",
        [
            _preset_field("full_name", "text", "Name", True, 1, "half_left"),
            _preset_field("email", "email", "Email", True, 2, "half_right"),
            _preset_field("company", "text", "Company", False, 3, "half_left"),
            _preset_field("subject", "text", "Subject", True, 4, "half_right"),
            _preset_field(
                "project_context",
                "textarea",
                "Project Context",
                True,
                5,
                "full",
                placeholder="Describe your constraints, timeline, and target outcomes...",
            ),
        ],
    ),
    _preset(
        "Newsletter",
        "newsletter",
        "Subscribe to our newsletter.",
        "You're subscribed! Welcome aboard.",
        [
            _preset_field("full_name", "text", "Name", True, 1, "half_left"),
            _preset_field("email", "email", "Email", True, 2, "half_right"),
        ],
    ),
    _preset(
        "Feedback",
        "feedback",
        "Share your feedback with us.",
        "Thank you for your feedback!",
        [
            _preset_field("full_name", "text", "Name", False, 1, "half_left"),
            _preset_field("email", "email", "Email", False, 2, "half_right"),
            _preset_field(
                "rating", "select", "Rating", True, 3, "full", options=_RATING_OPTIONS
            ),
            _preset_field("message", "textarea", "Message", True, 4, "full"),
        ],
    ),
    _preset(
        "Support",
        "support",
        "Submit a support request.",
        "Your support request has been received. We'll get back to you shortly.",
        [
            _preset_field("full_name", "text", "Name", True, 1, "half_left"),
            _preset_field("email", "email", "Email", True, 2, "half_right"),
            _preset_field("subject", "text", "Subject", True, 3, "full"),
            _preset_field(
                "priority",
                "select",
                "Priority",
                True,
                4,
                "half_left",
                options=_PRIORITY_OPTIONS,
            ),
            _preset_field("description", "textarea", "Description", True, 5, "full"),
        ],
    ),
]


def seed_forms(apps: Any, schema_editor: Any) -> None:
    """Seed four preset forms with System-org ownership, idempotently."""
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")
    Form = apps.get_model("quickscale_modules_forms", "Form")
    FormField = apps.get_model("quickscale_modules_forms", "FormField")
    try:
        system_org = Organization.objects.get(is_system=True, slug="__system__")
    except Organization.DoesNotExist:
        system_org = Organization.objects.create(
            name="System", slug="__system__", is_system=True, is_personal=False
        )
    for preset in _PRESETS:
        form, created = Form.objects.get_or_create(
            slug=preset["slug"],
            defaults={
                "title": preset["title"],
                "description": preset["description"],
                "success_message": preset["success_message"],
                "notify_emails": preset["notify_emails"],
                "organization": system_org,
                "data_retention_days": 365,
                "is_active": True,
                "spam_protection_enabled": True,
            },
        )
        if not created and form.organization_id is None:
            form.organization = system_org
            form.save(update_fields=["organization"])
        for field_data in preset["fields"]:
            defaults = {
                "field_type": field_data["field_type"],
                "label": field_data["label"],
                "required": field_data.get("required", False),
                "order": field_data["order"],
                "layout_hint": field_data.get("layout_hint", "full"),
                "placeholder": field_data.get("placeholder", ""),
                "options": field_data.get("options", []),
                "validation_rules": field_data.get("validation_rules", {}),
                "organization": system_org,
            }
            FormField.objects.get_or_create(
                form=form, name=field_data["name"], defaults=defaults
            )


def reverse_seed(apps: Any, schema_editor: Any) -> None:
    del apps, schema_editor


def _add_composite_fk(
    schema_editor: Any,
    child_table: str,
    constraint: str,
    child_fk_column: str,
    parent_table: str,
    on_delete: str,
) -> None:
    schema_editor.execute(
        f"ALTER TABLE {child_table} ADD CONSTRAINT {constraint} "
        f"FOREIGN KEY ({child_fk_column}, organization_id) "
        f"REFERENCES {parent_table}(id, organization_id) "
        f"ON DELETE {on_delete} NOT DEFERRABLE NOT VALID"
    )
    schema_editor.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}")


def _install_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add composite child FKs and enable FORCE RLS for Forms tables."""
    del apps
    _add_composite_fk(
        schema_editor,
        FORMS_FORMFIELD_TABLE,
        FORMS_FORMFIELD_FORM_ORG_FK,
        "form_id",
        FORMS_FORM_TABLE,
        "CASCADE",
    )
    _add_composite_fk(
        schema_editor,
        FORMS_FORMSUBMISSION_TABLE,
        FORMS_FORMSUBMISSION_FORM_ORG_FK,
        "form_id",
        FORMS_FORM_TABLE,
        "RESTRICT",
    )
    _add_composite_fk(
        schema_editor,
        FORMS_FORMFIELDVALUE_TABLE,
        FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK,
        "submission_id",
        FORMS_FORMSUBMISSION_TABLE,
        "CASCADE",
    )
    _add_composite_fk(
        schema_editor,
        FORMS_FORMFIELDVALUE_TABLE,
        FORMS_FORMFIELDVALUE_FIELD_ORG_FK,
        "field_id",
        FORMS_FORMFIELD_TABLE,
        "SET NULL (field_id)",
    )


def _uninstall_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse the Forms composite FKs."""
    del apps
    for table, constraint in (
        (FORMS_FORMFIELD_TABLE, FORMS_FORMFIELD_FORM_ORG_FK),
        (FORMS_FORMSUBMISSION_TABLE, FORMS_FORMSUBMISSION_FORM_ORG_FK),
        (FORMS_FORMFIELDVALUE_TABLE, FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK),
        (FORMS_FORMFIELDVALUE_TABLE, FORMS_FORMFIELDVALUE_FIELD_ORG_FK),
    ):
        remove_composite_child_fk(
            schema_editor, child_table=table, constraint_name=constraint
        )


def _forward_refresh_rls_nullif(apps: Any, schema_editor: Any) -> None:
    """Re-create Forms policies from the NULLIF-guarded template."""
    del apps
    revert_force_rls(schema_editor, _FORMS_ALL_RLS_TARGETS)
    apply_force_rls(schema_editor, _FORMS_ALL_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
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
                ("slug", models.SlugField()),
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
                        default=quickscale_modules_forms.models.get_default_form_data_retention_days,
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="forms",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_form",
                "ordering": ["title"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="form_fields",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formfield",
                "ordering": ["order"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="form_submissions",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formsubmission",
                "ordering": ["-submitted_at"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="form_field_values",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "db_table": "quickscale_modules_forms_formfieldvalue",
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.AddConstraint(
            model_name="form",
            constraint=models.UniqueConstraint(
                fields=("slug", "organization"),
                name="quickscale_modules_forms_form_slug_organization_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="form",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"), name="forms_form_id_org_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="formfield",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"), name="forms_formfield_id_org_unique"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="formfield",
            unique_together={("form", "name")},
        ),
        migrations.AddConstraint(
            model_name="formsubmission",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"), name="forms_formsubmission_id_org_unique"
            ),
        ),
        migrations.RunPython(
            code=seed_forms,
            reverse_code=reverse_seed,
        ),
        migrations.RunPython(
            code=_install_composite_fks_and_rls,
            reverse_code=_uninstall_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
        migrations.RunPython(
            code=_forward_refresh_rls_nullif,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
