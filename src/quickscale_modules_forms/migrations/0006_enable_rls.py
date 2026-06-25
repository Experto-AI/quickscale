"""Enable and FORCE PostgreSQL Row-Level Security on Forms tables.

T1.13 — Add DB-level RLS for Forms tables as a defense-in-depth layer
below the Django-level TenantManager.

Forward:
    1. ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY on the Form
       table (the org-ownership root) so that RLS applies to every role
       including the table owner (Django connection).
    2. CREATE POLICY that uses ``current_setting('app.current_org_id', true)::uuid``
       for SELECT, INSERT, UPDATE, and DELETE.

Reverse:
    1. DROP the per-table policy.
    2. ALTER TABLE … NO FORCE ROW LEVEL SECURITY.
    3. ALTER TABLE … DISABLE ROW LEVEL SECURITY.

FormField, FormSubmission, and FormFieldValue do not carry their own
``organization_id`` column — they are scoped through the Form FK.
RLS on Form is the isolation boundary; child tables are accessed only via
forms that pass the Form-level RLS policy.

All admin reads/mutations on Form must set ``app.current_org_id``
(and the ContextVar) inside a transaction before querying.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

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

# ---------------------------------------------------------------------------
# Forward
# ---------------------------------------------------------------------------

_FORWARD_SQL = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY {policy_name} ON {table}
    FOR ALL
    USING (current_setting('app.current_org_id', true)::uuid = organization_id)
    WITH CHECK (current_setting('app.current_org_id', true)::uuid = organization_id);
"""


def _forward(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, policy in _FORMS_RLS_TARGETS:
        schema_editor.execute(
            _FORWARD_SQL.format(table=table, policy_name=policy),
        )


# ---------------------------------------------------------------------------
# Reverse
# ---------------------------------------------------------------------------

_REVERSE_SQL = """
DROP POLICY IF EXISTS {policy_name} ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


def _reverse(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, policy in _FORMS_RLS_TARGETS:
        schema_editor.execute(
            _REVERSE_SQL.format(table=table, policy_name=policy),
        )


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
