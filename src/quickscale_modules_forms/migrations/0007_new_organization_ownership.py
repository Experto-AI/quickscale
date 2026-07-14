"""Add direct organization ownership to FormField, FormSubmission, and FormFieldValue (AF1 Phase 4 / AF12 Phase 1).

Schema changes:
  - Add NOT NULL ``organization`` FK (PROTECT) to FormField, FormSubmission,
    and FormFieldValue.
  - Backfill existing rows from the parent Form / FormSubmission.
  - Add UNIQUE (id, organization_id) constraints on Form, FormField, and
    FormSubmission (parent tables).
  - Add DB-only composite FOREIGN KEYs enforcing child-parent org equality:
      FormField(form_id, organization_id) → Form(id, organization_id)
      FormSubmission(form_id, organization_id) → Form(id, organization_id)
      FormFieldValue(submission_id, organization_id) → FormSubmission(id, organization_id)
      FormFieldValue(field_id, organization_id) → FormField(id, organization_id)
        (partial-column SET NULL on field_id when parent FormField is deleted)
  - Enable and FORCE PostgreSQL Row-Level Security on all three tables.

After this migration, FormField, FormSubmission, and FormFieldValue are
direct-owned tenant tables:
  - ``objects`` = TenantManager()
  - ``all_objects`` = TenantManager(super_scope=True)
  - live FORCE-RLS policy on ``organization_id``
  - DB-level composite FKs enforcing child-parent ``organization_id`` equality.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    add_parent_unique_constraint,
    apply_force_rls,
    operator_access_migration,
    remove_composite_child_fk,
    remove_parent_unique_constraint,
    revert_force_rls,
)

# ---------------------------------------------------------------------------
# Table names (explicit db_table from models.py Meta)
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
# Constraint names (AF12 Phase 1 naming contract)
# ---------------------------------------------------------------------------
FORMS_FORM_ID_ORG_UNIQUE = "forms_form_id_org_unique"
FORMS_FORMFIELD_ID_ORG_UNIQUE = "forms_formfield_id_org_unique"
FORMS_FORMSUBMISSION_ID_ORG_UNIQUE = "forms_formsubmission_id_org_unique"

FORMS_FORMFIELD_FORM_ORG_FK = "forms_formfield_form_org_fk"
FORMS_FORMSUBMISSION_FORM_ORG_FK = "forms_formsubmission_form_org_fk"
FORMS_FORMFIELDVALUE_SUBMISSION_ORG_FK = "forms_formfieldvalue_submission_org_fk"
FORMS_FORMFIELDVALUE_FIELD_ORG_FK = "forms_formfieldvalue_field_org_fk"

# ---------------------------------------------------------------------------
# Backfill helpers
# ---------------------------------------------------------------------------


def _backfill_formfield_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Form to FormField rows.

    Uses raw SQL with a System-org fallback so that rows whose parent
    Form also has no organization (e.g. seed data created before the
    organization column existed in migration 0004) still receive a valid
    org ID — matching the ``assign_system_org`` pattern from 0005.

    SA79 (CR-SA79-001 RESOLVED): Sets the ``app.operator_access`` GUC
    before the backfill so the correlated subquery on Form is not blocked
    by FORCE RLS (enabled in 0006) when the connected role has NOBYPASSRLS.
    Unlike the first-pass fix that pinned ``app.current_org_id`` to the
    System org (which only made System-org Form rows visible), using
    ``app.operator_access`` enables the read-only OR clause in the Form
    RLS policy (``FOR SELECT``), making **all** Form rows visible
    regardless of their organization — so non-system tenant data is
    correctly backfilled with the parent Form's real org.

    SA88: The ``operator_access_migration`` context manager from
    ``quickscale_modules_orgs.tenancy`` encapsulates this SET LOCAL
    pattern.  Each backfill function independently wraps its DML in
    ``with operator_access_migration(schema_editor)`` for lexical proof
    that every cross-table write assigning ``organization_id`` is
    covered.  The conformance gate ``test_sa88_migration_operator_access_conformance``
    AST-parses this migration and requires lexical enclosure by
    ``with operator_access_migration(schema_editor)`` for all cross-table
    DML assigning ``organization_id``.

    The ``operator_access_migration`` context manager captures the prior
    GUC on entry and lexically restores it in ``finally`` via
    ``set_config(..., is_local=true)``.  Each wrapper independently
    elevates and restores; no GUC value leaks between sequential wrappers
    or beyond the enclosing scope.
    """
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")
    try:
        system_org = Organization.objects.get(is_system=True, slug="__system__")
    except Organization.DoesNotExist:
        system_org = Organization.objects.create(
            name="System",
            slug="__system__",
            is_system=True,
            is_personal=False,
        )

    # SA79 + SA88: Use operator_access_migration() so the correlated
    # subqueries on Form are not blocked by FORCE RLS (enabled in 0006)
    # when the connected role has NOBYPASSRLS.
    # Each backfill function independently wraps in
    # operator_access_migration() — the context manager lexically
    # restores the prior GUC on exit via set_config(..., is_local=true)
    # so each wrapper self-contains its operator_access elevation.
    with operator_access_migration(schema_editor):
        # Ensure Form itself is backfilled (defensive — 0005 covers this
        # but the migration executor may process app migrations in an
        # order that leaves Form rows without org during test DB creation).
        schema_editor.execute(
            "UPDATE quickscale_modules_forms_form "
            "SET organization_id = %s "
            "WHERE organization_id IS NULL",
            [system_org.pk],
        )

        # Copy org from the parent Form, falling back to System org for
        # any rows whose parent Form was seeded before the org column existed.
        # With ``operator_access`` active, the subquery sees ALL Form rows,
        # so non-system tenant data is correctly backfilled.
        schema_editor.execute(
            "UPDATE quickscale_modules_forms_formfield "
            "SET organization_id = COALESCE("
            "  (SELECT f.organization_id FROM quickscale_modules_forms_form f "
            "   WHERE f.id = quickscale_modules_forms_formfield.form_id),"
            "  %s"
            ") "
            "WHERE organization_id IS NULL",
            [system_org.pk],
        )


def _backfill_formsubmission_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent Form to FormSubmission rows.

    SA88: Wrapped in operator_access_migration for lexical proof that
    the correlated subquery on Form (FORCE RLS enabled in 0006) is
    covered under NOBYPASSRLS.  The context manager lexically restores
    the prior GUC on exit; each wrapper in this migration independently
    elevates and restores.
    """
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE quickscale_modules_forms_formsubmission "
            "SET organization_id = ("
            "  SELECT f.organization_id FROM quickscale_modules_forms_form f "
            "  WHERE f.id = quickscale_modules_forms_formsubmission.form_id"
            ") "
            "WHERE organization_id IS NULL"
        )


def _backfill_formfieldvalue_org(apps: Any, schema_editor: Any) -> None:
    """Copy organization_id from the parent FormSubmission to FormFieldValue rows.

    SA88: Wrapped in operator_access_migration for lexical proof that
    the correlated subquery on FormSubmission (FORCE RLS enabled in
    0006) is covered under NOBYPASSRLS.  The context manager lexically
    restores the prior GUC on exit.
    """
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE quickscale_modules_forms_formfieldvalue "
            "SET organization_id = ("
            "  SELECT fs.organization_id "
            "  FROM quickscale_modules_forms_formsubmission fs "
            "  WHERE fs.id = quickscale_modules_forms_formfieldvalue.submission_id"
            ") "
            "WHERE organization_id IS NULL"
        )


def _assert_no_null_org(apps: Any, schema_editor: Any) -> None:
    """Guard: fail the migration if any row still has NULL organization."""
    null_counts: list[str] = []
    for name, table in [
        ("FormField", "quickscale_modules_forms_formfield"),
        ("FormSubmission", "quickscale_modules_forms_formsubmission"),
        ("FormFieldValue", "quickscale_modules_forms_formfieldvalue"),
    ]:
        with schema_editor.connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE organization_id IS NULL")
            count = cur.fetchone()[0]
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
# Composite FK + RLS helpers (AF12 Phase 1)
# ---------------------------------------------------------------------------


def _install_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add parent unique constraints, composite child FKs, and enable FORCE RLS.

    Composite FKs are added with NOT VALID (skipping the validation scan
    during creation) and then explicitly validated with VALIDATE CONSTRAINT
    after each FK is installed.  The backfill has already completed in an
    earlier migration step, so all existing rows carry a valid
    organization_id.  This two-step pattern avoids blocking table scans
    during FK creation while guaranteeing the constraint holds across all
    existing data.
    """
    del apps

    # SA88: Use operator_access_migration context manager instead of raw
    # SET LOCAL.  The context manager captures and restores the GUC
    # lexically via set_config(..., is_local=true), eliminating the risk
    # of bare GUC manipulation that the conformance gate rejects.
    with operator_access_migration(schema_editor):
        # 1. Add UNIQUE (id, organization_id) on parent tables.
        add_parent_unique_constraint(
            schema_editor,
            table=FORMS_FORM_TABLE,
            constraint_name=FORMS_FORM_ID_ORG_UNIQUE,
        )
        add_parent_unique_constraint(
            schema_editor,
            table=FORMS_FORMFIELD_TABLE,
            constraint_name=FORMS_FORMFIELD_ID_ORG_UNIQUE,
        )
        add_parent_unique_constraint(
            schema_editor,
            table=FORMS_FORMSUBMISSION_TABLE,
            constraint_name=FORMS_FORMSUBMISSION_ID_ORG_UNIQUE,
        )

        # 2. Add composite child FKs with NOT VALID, then validate each one.
        #    Backfill is complete (steps 2–3 above), so validation guarantees
        #    the constraint holds across all existing data.
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

        def _validate_fk(
            child_table: str,
            constraint: str,
        ) -> None:
            schema_editor.execute(
                f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}"
            )

        #    FormField → Form (ON DELETE CASCADE matches Django FK)
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
        #    FormSubmission → Form (ON DELETE RESTRICT matches Django FK PROTECT)
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
        #    FormFieldValue → FormSubmission (ON DELETE CASCADE matches Django FK)
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

        # 3. FormFieldValue → FormField: special partial-column SET NULL.
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

        # 4. Enable FORCE RLS on all three tables.
        apply_force_rls(schema_editor, _FORMS_RLS_TARGETS)


def _uninstall_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop RLS policies, drop composite FKs, drop parent unique constraints."""
    del apps

    # 1. Revert FORCE RLS (drop policies, disable RLS).
    revert_force_rls(schema_editor, _FORMS_RLS_TARGETS)

    # 2. Drop composite child FKs.
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

    # 3. Drop parent unique constraints.
    remove_parent_unique_constraint(
        schema_editor,
        table=FORMS_FORM_TABLE,
        constraint_name=FORMS_FORM_ID_ORG_UNIQUE,
    )
    remove_parent_unique_constraint(
        schema_editor,
        table=FORMS_FORMFIELD_TABLE,
        constraint_name=FORMS_FORMFIELD_ID_ORG_UNIQUE,
    )
    remove_parent_unique_constraint(
        schema_editor,
        table=FORMS_FORMSUBMISSION_TABLE,
        constraint_name=FORMS_FORMSUBMISSION_ID_ORG_UNIQUE,
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
        # ---- Step 5: Add parent unique constraints, composite FKs, enable RLS ----
        migrations.RunPython(
            code=_install_composite_fks_and_rls,
            reverse_code=_uninstall_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
    ]
