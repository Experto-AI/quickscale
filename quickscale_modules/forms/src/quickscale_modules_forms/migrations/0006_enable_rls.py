"""Enable and FORCE PostgreSQL Row-Level Security on Forms tables.

T1.13 — Add DB-level RLS for Forms tables as a defense-in-depth layer
below the Django-level TenantManager.

FormField, FormSubmission, and FormFieldValue do not carry their own
``organization_id`` column — they are scoped through the Form FK.
RLS on Form is the isolation boundary; child tables are accessed only via
forms that pass the Form-level RLS policy.

Uses the shared ``apply_force_rls`` / ``revert_force_rls`` helpers from
``quickscale_modules_orgs.tenancy`` instead of duplicating SQL.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

# ---------------------------------------------------------------------------
# Policy names
# ---------------------------------------------------------------------------
FORMS_FORM_RLS_POLICY = "forms_form_org_isolation"

# ---------------------------------------------------------------------------
# Table names (explicit db_table from models.py Meta)
# ---------------------------------------------------------------------------
FORMS_FORM_TABLE = "quickscale_modules_forms_form"

# ---------------------------------------------------------------------------
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_FORMS_RLS_TARGETS = ((FORMS_FORM_TABLE, FORMS_FORM_RLS_POLICY),)


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _FORMS_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _FORMS_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on Form table (T1.13)."""

    dependencies = [
        (
            "quickscale_modules_forms",
            "0005_form_alter_organization_not_null_protect",
        ),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            hints={"target_db": "default"},
        ),
    ]
