"""Add direct organization ownership to FormField, FormSubmission, and FormFieldValue (AF1 Phase 4).

Schema changes:
  - Add NOT NULL ``organization`` FK (PROTECT) to FormField, FormSubmission,
    and FormFieldValue.
  - Backfill existing rows from the parent Form / FormSubmission.
  - Install/ensure the shared child-parent equality trigger function.
  - Enable BEFORE INSERT OR UPDATE triggers that enforce:
      FormField.organization_id = Form.organization_id
      FormSubmission.organization_id = Form.organization_id
      FormFieldValue.organization_id = FormSubmission.organization_id
      FormFieldValue.organization_id = FormField.organization_id
        (conditional — only when field_id IS NOT NULL)
  - Enable and FORCE PostgreSQL Row-Level Security on all three tables.

After this migration, FormField, FormSubmission, and FormFieldValue are
direct-owned tenant tables:
  - ``objects`` = TenantManager()
  - ``all_objects`` = TenantManager(super_scope=True)
  - live FORCE-RLS policy on ``organization_id``
  - DB-level child-parent equality triggers against the parent table,
    plus conditional parity to FormField for FormFieldValue.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    CHILD_PARENT_EQUALITY_FUNC_NAME,
    CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX,
    apply_force_rls,
    disable_child_parent_equality,
    enable_child_parent_equality,
    install_equality_trigger_function,
    revert_force_rls,
)

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
FORMS_FORM_TABLE = "quickscale_modules_forms_form"
FORMS_FORMFIELD_TABLE = "quickscale_modules_forms_formfield"
FORMS_FORMSUBMISSION_TABLE = "quickscale_modules_forms_formsubmission"
FORMS_FORMFIELDVALUE_TABLE = "quickscale_modules_forms_formfieldvalue"

FORMS_FORMFIELD_RLS_POLICY = "forms_formfield_org_isolation"
FORMS_FORMSUBMISSION_RLS_POLICY = "forms_formsubmission_org_isolation"
FORMS_FORMFIELDVALUE_RLS_POLICY = "forms_formfieldvalue_org_isolation"

_FORMS_RLS_TARGETS = (
    (FORMS_FORMFIELD_TABLE, FORMS_FORMFIELD_RLS_POLICY),
    (FORMS_FORMSUBMISSION_TABLE, FORMS_FORMSUBMISSION_RLS_POLICY),
    (FORMS_FORMFIELDVALUE_TABLE, FORMS_FORMFIELDVALUE_RLS_POLICY),
)

# ---------------------------------------------------------------------------
# Backfill helpers
# ---------------------------------------------------------------------------


def _backfill_formfield_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Form to FormField rows."""
    del schema_editor
    FormField_model = apps.get_model("quickscale_modules_forms", "FormField")
    Form_model = apps.get_model("quickscale_modules_forms", "Form")
    for field in FormField_model._base_manager.filter(
        organization__isnull=True
    ).iterator():
        try:
            parent = Form_model._base_manager.get(pk=field.form_id)
        except Form_model.DoesNotExist:
            continue
        FormField_model._base_manager.filter(pk=field.pk).update(
            organization_id=parent.organization_id
        )


def _backfill_formsubmission_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Form to FormSubmission rows."""
    del schema_editor
    FormSubmission_model = apps.get_model("quickscale_modules_forms", "FormSubmission")
    Form_model = apps.get_model("quickscale_modules_forms", "Form")
    for sub in FormSubmission_model._base_manager.filter(
        organization__isnull=True
    ).iterator():
        try:
            parent = Form_model._base_manager.get(pk=sub.form_id)
        except Form_model.DoesNotExist:
            continue
        FormSubmission_model._base_manager.filter(pk=sub.pk).update(
            organization_id=parent.organization_id
        )


def _backfill_formfieldvalue_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent FormSubmission to FormFieldValue rows."""
    del schema_editor
    FormFieldValue_model = apps.get_model("quickscale_modules_forms", "FormFieldValue")
    FormSubmission_model = apps.get_model("quickscale_modules_forms", "FormSubmission")
    for fv in FormFieldValue_model._base_manager.filter(
        organization__isnull=True
    ).iterator():
        try:
            parent = FormSubmission_model._base_manager.get(pk=fv.submission_id)
        except FormSubmission_model.DoesNotExist:
            continue
        FormFieldValue_model._base_manager.filter(pk=fv.pk).update(
            organization_id=parent.organization_id
        )


def _assert_no_null_org(apps: Any, schema_editor: Any) -> None:
    """Guard: fail the migration if any row still has NULL organization."""
    del schema_editor
    models_info = [
        ("FormField", apps.get_model("quickscale_modules_forms", "FormField")),
        (
            "FormSubmission",
            apps.get_model("quickscale_modules_forms", "FormSubmission"),
        ),
        (
            "FormFieldValue",
            apps.get_model("quickscale_modules_forms", "FormFieldValue"),
        ),
    ]
    null_counts: list[str] = []
    for name, model in models_info:
        count = model._base_manager.filter(organization__isnull=True).count()
        if count:
            null_counts.append(f"{name}={count}")

    if null_counts:
        raise RuntimeError(
            "Migration 0007 cannot set NOT NULL on organization "
            "while NULL-owned rows remain: "
            + ", ".join(null_counts)
            + ". Backfill organization ownership for these rows before "
            "applying the AF1 Phase 4 schema flip."
        )


# ---------------------------------------------------------------------------
# Equality + RLS helpers
# ---------------------------------------------------------------------------


def _install_equality_and_rls(apps: Any, schema_editor: Any) -> None:
    """Install equality trigger function, enable triggers, and enable FORCE RLS."""
    del apps

    # 1. Install/refresh the shared trigger function (idempotent).
    install_equality_trigger_function(schema_editor)

    # 2. Enable child-parent equality triggers.
    #    FormField → Form (form_id FK)
    enable_child_parent_equality(
        schema_editor,
        child_table=FORMS_FORMFIELD_TABLE,
        parent_table=FORMS_FORM_TABLE,
        child_fk_column="form_id",
    )
    #    FormSubmission → Form (form_id FK)
    enable_child_parent_equality(
        schema_editor,
        child_table=FORMS_FORMSUBMISSION_TABLE,
        parent_table=FORMS_FORM_TABLE,
        child_fk_column="form_id",
    )
    #    FormFieldValue → FormSubmission (submission_id FK) — always
    enable_child_parent_equality(
        schema_editor,
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        parent_table=FORMS_FORMSUBMISSION_TABLE,
        child_fk_column="submission_id",
    )

    # 3. Enable conditional parity trigger on FormFieldValue → FormField.
    #    Only fires when field_id IS NOT NULL (SET_NULL contract).
    _enable_conditional_field_parity(schema_editor)

    # 4. Enable FORCE RLS on all three tables.
    apply_force_rls(schema_editor, _FORMS_RLS_TARGETS)


def _uninstall_equality_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop RLS policies, drop triggers (function is kept)."""
    del apps

    # 1. Revert FORCE RLS (drop policies, disable RLS).
    revert_force_rls(schema_editor, _FORMS_RLS_TARGETS)

    # 2. Drop equality triggers.
    for child_table in (
        FORMS_FORMFIELD_TABLE,
        FORMS_FORMSUBMISSION_TABLE,
        FORMS_FORMFIELDVALUE_TABLE,
    ):
        disable_child_parent_equality(
            schema_editor,
            child_table=child_table,
        )

    # 3. Drop the conditional parity trigger on FormFieldValue.
    _disable_conditional_field_parity(schema_editor)

    # Note: the shared trigger function is left in place — it may be
    # used by other tables and is simply kept as a no-op function.


# ---------------------------------------------------------------------------
# Conditional parity trigger for FormFieldValue → FormField
# ---------------------------------------------------------------------------
# When field_id IS NOT NULL, enforce:
#   FormFieldValue.organization_id = FormField.organization_id
#
# PostgreSQL supports a WHEN clause on triggers to make them conditional.
# We use the shared trigger function with field_id as the FK column but
# only fire it when field_id IS NOT NULL, preserving the SET_NULL contract.
# ---------------------------------------------------------------------------

_CONDITIONAL_TRIGGER_NAME = (
    f"{CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX}"
    f"{FORMS_FORMFIELDVALUE_TABLE}_field_org_equality"
)

_CONDITIONAL_TRIGGER_SQL = """
CREATE TRIGGER {trigger_name}
BEFORE INSERT OR UPDATE
ON {child_table}
FOR EACH ROW
WHEN (NEW.field_id IS NOT NULL)
EXECUTE FUNCTION {func_name}(
    '{parent_table}',
    '{child_fk_column}',
    '{org_column}'
);
"""


def _enable_conditional_field_parity(schema_editor: Any) -> None:
    """Create a conditional trigger enforcing FormFieldValue → FormField org parity.

    This trigger only fires when ``field_id`` is non-null, preserving the
    SET_NULL contract for historical field values whose definition was deleted.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    sql = _CONDITIONAL_TRIGGER_SQL.format(
        trigger_name=_CONDITIONAL_TRIGGER_NAME,
        child_table=FORMS_FORMFIELDVALUE_TABLE,
        func_name=CHILD_PARENT_EQUALITY_FUNC_NAME,
        parent_table=FORMS_FORMFIELD_TABLE,
        child_fk_column="field_id",
        org_column="organization_id",
    )
    schema_editor.execute(sql)


def _disable_conditional_field_parity(schema_editor: Any) -> None:
    """Drop the conditional parity trigger from FormFieldValue."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {_CONDITIONAL_TRIGGER_NAME} ON {FORMS_FORMFIELDVALUE_TABLE};"
    )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Add direct organization ownership to FormField, FormSubmission, and FormFieldValue."""

    dependencies = [
        ("quickscale_modules_forms", "0006_enable_rls"),
        ("quickscale_modules_orgs", "0004_organizationtombstone"),
    ]

    operations = [
        # ---- Step 1: Add nullable organization FK ----
        migrations.AddField(
            model_name="formfield",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="form_fields",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="formsubmission",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="form_submissions",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="formfieldvalue",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="form_field_values",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        # ---- Step 2: Backfill from parent Form / FormSubmission ----
        migrations.RunPython(
            code=_backfill_formfield_org,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            code=_backfill_formsubmission_org,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            code=_backfill_formfieldvalue_org,
            reverse_code=migrations.RunPython.noop,
        ),
        # ---- Step 3: Guard against NULL rows before setting NOT NULL ----
        migrations.RunPython(
            code=_assert_no_null_org,
            reverse_code=migrations.RunPython.noop,
        ),
        # ---- Step 4: Make NOT NULL + PROTECT ----
        migrations.AlterField(
            model_name="formfield",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="form_fields",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="formsubmission",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="form_submissions",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="formfieldvalue",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="form_field_values",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        # ---- Step 5: Install equality triggers and enable RLS ----
        migrations.RunPython(
            code=_install_equality_and_rls,
            reverse_code=_uninstall_equality_and_rls,
            hints={"target_db": "default"},
        ),
    ]
