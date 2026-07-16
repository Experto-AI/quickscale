"""Initial migration for the QuickScale Forms module.

Collapsed SA92 migration: final-schema 0001 with Form, FormField,
FormSubmission, and FormFieldValue models.  Operation order is
schema → narrow preset bootstrap → RLS/composite FKs.

Schema includes NOT NULL/PROTECT organization FK on all 4 models,
named parent UNIQUE constraints (forms_form_id_org_unique,
forms_formfield_id_org_unique, forms_formsubmission_id_org_unique),
named composite child FKs:
  - forms_formfield_form_org_fk CASCADE
  - forms_formsubmission_form_org_fk RESTRICT
  - forms_formfieldvalue_submission_org_fk CASCADE
  - forms_formfieldvalue_field_org_fk SET NULL(field_id)

Bootstrap creates System org (if absent) and 4 preset forms
(contact/newsletter/feedback/support) with 16 fields, 365-day
retention, and System-org ownership.  Idempotent via get_or_create.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import django.db.models.manager
from quickscale_modules_forms.models import get_default_form_data_retention_days
from quickscale_modules_orgs.tenancy import (
    apply_force_rls,
    remove_composite_child_fk,
    revert_force_rls,
)

# ---------------------------------------------------------------------------
# Table names (explicit db_table from models.py Meta)
# ---------------------------------------------------------------------------
FORMS_FORM_TABLE = "quickscale_modules_forms_form"
FORMS_FORMFIELD_TABLE = "quickscale_modules_forms_formfield"
FORMS_FORMSUBMISSION_TABLE = "quickscale_modules_forms_formsubmission"
FORMS_FORMFIELDVALUE_TABLE = "quickscale_modules_forms_formfieldvalue"

# ---------------------------------------------------------------------------
# RLS policy names
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Constraint names
# ---------------------------------------------------------------------------
FORMS_FORM_ID_ORG_UNIQUE = "forms_form_id_org_unique"
FORMS_FORMFIELD_ID_ORG_UNIQUE = "forms_formfield_id_org_unique"
FORMS_FORMSUBMISSION_ID_ORG_UNIQUE = "forms_formsubmission_id_org_unique"
FORMS_FORMFIELD_FORM_ORG_FK = "forms_formfield_form_org_fk"
FORMS_FORMSUBMISSION_FORM_ORG_FK = "forms_formsubmission_form_org_fk"
FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK = "forms_formfieldvalue_submission_org_fk"
FORMS_FORMFIELDVALUE_FIELD_ORG_FK = "forms_formfieldvalue_field_org_fk"

# ---------------------------------------------------------------------------
# Bootstrap presets — 4 forms, 16 fields total
# ---------------------------------------------------------------------------
_PRESETS = [
    {
        "title": "Contact",
        "slug": "contact",
        "description": "Get in Touch — share your current constraints, timeline, and target outcomes.",
        "success_message": "Thank you, we will respond within 24 hours.",
        "notify_emails": "",
        "fields": [
            {
                "name": "full_name",
                "field_type": "text",
                "label": "Name",
                "required": True,
                "order": 1,
                "layout_hint": "half_left",
            },
            {
                "name": "email",
                "field_type": "email",
                "label": "Email",
                "required": True,
                "order": 2,
                "layout_hint": "half_right",
            },
            {
                "name": "company",
                "field_type": "text",
                "label": "Company",
                "required": False,
                "order": 3,
                "layout_hint": "half_left",
            },
            {
                "name": "subject",
                "field_type": "text",
                "label": "Subject",
                "required": True,
                "order": 4,
                "layout_hint": "half_right",
            },
            {
                "name": "project_context",
                "field_type": "textarea",
                "label": "Project Context",
                "required": True,
                "order": 5,
                "layout_hint": "full",
                "placeholder": "Describe your constraints, timeline, and target outcomes...",
            },
        ],
    },
    {
        "title": "Newsletter",
        "slug": "newsletter",
        "description": "Subscribe to our newsletter.",
        "success_message": "You're subscribed! Welcome aboard.",
        "notify_emails": "",
        "fields": [
            {
                "name": "full_name",
                "field_type": "text",
                "label": "Name",
                "required": True,
                "order": 1,
                "layout_hint": "half_left",
            },
            {
                "name": "email",
                "field_type": "email",
                "label": "Email",
                "required": True,
                "order": 2,
                "layout_hint": "half_right",
            },
        ],
    },
    {
        "title": "Feedback",
        "slug": "feedback",
        "description": "Share your feedback with us.",
        "success_message": "Thank you for your feedback!",
        "notify_emails": "",
        "fields": [
            {
                "name": "full_name",
                "field_type": "text",
                "label": "Name",
                "required": False,
                "order": 1,
                "layout_hint": "half_left",
            },
            {
                "name": "email",
                "field_type": "email",
                "label": "Email",
                "required": False,
                "order": 2,
                "layout_hint": "half_right",
            },
            {
                "name": "rating",
                "field_type": "select",
                "label": "Rating",
                "required": True,
                "order": 3,
                "layout_hint": "full",
                "options": [
                    {"value": "1", "label": "1 — Poor"},
                    {"value": "2", "label": "2 — Fair"},
                    {"value": "3", "label": "3 — Good"},
                    {"value": "4", "label": "4 — Very Good"},
                    {"value": "5", "label": "5 — Excellent"},
                ],
            },
            {
                "name": "message",
                "field_type": "textarea",
                "label": "Message",
                "required": True,
                "order": 4,
                "layout_hint": "full",
            },
        ],
    },
    {
        "title": "Support",
        "slug": "support",
        "description": "Submit a support request.",
        "success_message": "Your support request has been received. We'll get back to you shortly.",
        "notify_emails": "",
        "fields": [
            {
                "name": "full_name",
                "field_type": "text",
                "label": "Name",
                "required": True,
                "order": 1,
                "layout_hint": "half_left",
            },
            {
                "name": "email",
                "field_type": "email",
                "label": "Email",
                "required": True,
                "order": 2,
                "layout_hint": "half_right",
            },
            {
                "name": "subject",
                "field_type": "text",
                "label": "Subject",
                "required": True,
                "order": 3,
                "layout_hint": "full",
            },
            {
                "name": "priority",
                "field_type": "select",
                "label": "Priority",
                "required": True,
                "order": 4,
                "layout_hint": "half_left",
                "options": [
                    {"value": "low", "label": "Low"},
                    {"value": "medium", "label": "Medium"},
                    {"value": "high", "label": "High"},
                ],
            },
            {
                "name": "description",
                "field_type": "textarea",
                "label": "Description",
                "required": True,
                "order": 5,
                "layout_hint": "full",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Bootstrap RunPython
# ---------------------------------------------------------------------------


def seed_forms(apps: Any, schema_editor: Any) -> None:
    """Seed 4 preset forms with System-org ownership, idempotently."""
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")
    Form = apps.get_model("quickscale_modules_forms", "Form")
    FormField = apps.get_model("quickscale_modules_forms", "FormField")

    # Get or create the System org.
    try:
        system_org = Organization.objects.get(is_system=True, slug="__system__")
    except Organization.DoesNotExist:
        system_org = Organization.objects.create(
            name="System",
            slug="__system__",
            is_system=True,
            is_personal=False,
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

        # Set organization on form if it somehow exists without one.
        if not created and form.organization_id is None:
            form.organization = system_org
            form.save(update_fields=["organization"])

        for field_data in preset["fields"]:
            field_defaults = {
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
                form=form,
                name=field_data["name"],
                defaults=field_defaults,
            )


def reverse_seed(apps: Any, schema_editor: Any) -> None:
    pass


# ---------------------------------------------------------------------------
# Composite FK + RLS RunPython
# ---------------------------------------------------------------------------


def _install_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add composite child FKs (parent unique constraints already exist) and enable FORCE RLS."""
    del apps

    # Composite child FKs — NOT VALID then validate
    def _add_fk_not_valid(
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
            f"ON DELETE {on_delete} "
            f"NOT DEFERRABLE "
            f"NOT VALID"
        )

    def _validate_fk(child_table: str, constraint: str) -> None:
        schema_editor.execute(
            f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}"
        )

    # FormField → Form (CASCADE matches Django FK)
    _add_fk_not_valid(
        child_table=FORMS_FORMFIELD_TABLE,
        constraint=FORMS_FORMFIELD_FORM_ORG_FK,
        child_fk_column="form_id",
        parent_table=FORMS_FORM_TABLE,
        on_delete="CASCADE",
    )
    _validate_fk(
        child_table=FORMS_FORMFIELD_TABLE,
        constraint=FORMS_FORMFIELD_FORM_ORG_FK,
    )

    # FormSubmission → Form (RESTRICT matches PROTECT)
    _add_fk_not_valid(
        child_table=FORMS_FORMSUBMISSION_TABLE,
        constraint=FORMS_FORMSUBMISSION_FORM_ORG_FK,
        child_fk_column="form_id",
        parent_table=FORMS_FORM_TABLE,
        on_delete="RESTRICT",
    )
    _validate_fk(
        child_table=FORMS_FORMSUBMISSION_TABLE,
        constraint=FORMS_FORMSUBMISSION_FORM_ORG_FK,
    )

    # FormFieldValue → FormSubmission (CASCADE)
    _add_fk_not_valid(
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint=FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK,
        child_fk_column="submission_id",
        parent_table=FORMS_FORMSUBMISSION_TABLE,
        on_delete="CASCADE",
    )
    _validate_fk(
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint=FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK,
    )

    # FormFieldValue → FormField (SET NULL on field_id)
    _add_fk_not_valid(
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint=FORMS_FORMFIELDVALUE_FIELD_ORG_FK,
        child_fk_column="field_id",
        parent_table=FORMS_FORMFIELD_TABLE,
        on_delete="SET NULL (field_id)",
    )
    _validate_fk(
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint=FORMS_FORMFIELDVALUE_FIELD_ORG_FK,
    )


def _uninstall_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop composite FKs (parent unique constraints and RLS managed separately)."""
    del apps

    # Drop composite child FKs
    remove_composite_child_fk(
        schema_editor,
        child_table=FORMS_FORMFIELD_TABLE,
        constraint_name=FORMS_FORMFIELD_FORM_ORG_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=FORMS_FORMSUBMISSION_TABLE,
        constraint_name=FORMS_FORMSUBMISSION_FORM_ORG_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint_name=FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        constraint_name=FORMS_FORMFIELDVALUE_FIELD_ORG_FK,
    )


def _forward_refresh_rls_nullif(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the NULLIF-guarded template."""
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
        # ---- Schema: Form ----
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
                        default=get_default_form_data_retention_days,
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
        # ---- Schema: FormField ----
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
        # ---- Schema: FormSubmission ----
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
        # ---- Schema: FormFieldValue ----
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
        # ---- Unique constraints: form + name on FormField ----
        migrations.AlterUniqueTogether(
            name="formfield",
            unique_together={("form", "name")},
        ),
        # ---- Slug + organization constraint on Form ----
        migrations.AddConstraint(
            model_name="form",
            constraint=models.UniqueConstraint(
                fields=("slug", "organization"),
                name="quickscale_modules_forms_form_slug_organization_unique",
            ),
        ),
        # ---- Parent unique constraints for composite FKs ----
        migrations.AddConstraint(
            model_name="form",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"),
                name="forms_form_id_org_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="formfield",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"),
                name="forms_formfield_id_org_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="formsubmission",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"),
                name="forms_formsubmission_id_org_unique",
            ),
        ),
        # ---- Bootstrap: seed 4 preset forms with System-org ownership ----
        # This runs before RLS is enabled on the Form table so the bootstrap
        # code can write without FORCE RLS interference.
        migrations.RunPython(
            code=seed_forms,
            reverse_code=reverse_seed,
        ),
        # ---- Step 1: Add composite child FKs for forms tables ----
        migrations.RunPython(
            code=_install_composite_fks_and_rls,
            reverse_code=_uninstall_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
        # ---- Step 2: Install FORCE RLS on all forms tables with current NULLIF-guarded template ----
        migrations.RunPython(
            code=_forward_refresh_rls_nullif,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
