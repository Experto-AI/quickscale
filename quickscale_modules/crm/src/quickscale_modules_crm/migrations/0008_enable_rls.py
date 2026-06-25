"""Enable and FORCE PostgreSQL Row-Level Security on CRM tables.

T1.11 — Add DB-level RLS for CRM tables as a defense-in-depth layer
below the Django-level TenantManager.

Forward:
    1. ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY on every
       org-owned CRM table so that RLS applies to every role including
       the table owner (Django connection).
    2. CREATE POLICY that uses ``current_setting('app.current_org_id', true)::uuid``
       for SELECT, INSERT, UPDATE, and DELETE.

Reverse:
    1. DROP the per-table policies.
    2. ALTER TABLE … NO FORCE ROW LEVEL SECURITY.
    3. ALTER TABLE … DISABLE ROW LEVEL SECURITY.

ContactNote and DealNote have no direct ``organization_id`` column — they are
scoped through their parent (Contact/Deal) FKs.  FORCE RLS on those tables is
therefore not applied here; the parent-derived scoping through Contact/Deal RLS
is the isolation boundary.  See T1.11 plan-review notes.

All admin reads/mutations on CRM tables must set ``app.current_org_id``
(and the ContextVar) inside a transaction before querying.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

# ---------------------------------------------------------------------------
# Policy names
# ---------------------------------------------------------------------------
CRM_TAG_RLS_POLICY = "crm_tag_org_isolation"
CRM_COMPANY_RLS_POLICY = "crm_company_org_isolation"
CRM_CONTACT_RLS_POLICY = "crm_contact_org_isolation"
CRM_STAGE_RLS_POLICY = "crm_stage_org_isolation"
CRM_DEAL_RLS_POLICY = "crm_deal_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
CRM_TAG_TABLE = "quickscale_modules_crm_tag"
CRM_COMPANY_TABLE = "quickscale_modules_crm_company"
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_STAGE_TABLE = "quickscale_modules_crm_stage"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"

# ---------------------------------------------------------------------------
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_CRM_RLS_TARGETS = (
    (CRM_TAG_TABLE, CRM_TAG_RLS_POLICY),
    (CRM_COMPANY_TABLE, CRM_COMPANY_RLS_POLICY),
    (CRM_CONTACT_TABLE, CRM_CONTACT_RLS_POLICY),
    (CRM_STAGE_TABLE, CRM_STAGE_RLS_POLICY),
    (CRM_DEAL_TABLE, CRM_DEAL_RLS_POLICY),
)

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
    for table, policy in _CRM_RLS_TARGETS:
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
    for table, policy in _CRM_RLS_TARGETS:
        schema_editor.execute(
            _REVERSE_SQL.format(table=table, policy_name=policy),
        )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on CRM tables (T1.11)."""

    dependencies = [
        ("quickscale_modules_crm", "0007_stage_terminal_semantic_bucket_unique"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            hints={"target_db": "default"},
        ),
    ]
