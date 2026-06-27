"""Enable and FORCE PostgreSQL Row-Level Security on CRM tables.

T1.11 — Add DB-level RLS for CRM tables as a defense-in-depth layer
below the Django-level TenantManager.

ContactNote and DealNote have no direct ``organization_id`` column — they are
scoped through their parent (Contact/Deal) FKs.  FORCE RLS on those tables is
therefore not applied here; the parent-derived scoping through Contact/Deal RLS
is the isolation boundary.  See T1.11 plan-review notes.

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


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _CRM_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _CRM_RLS_TARGETS)


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
