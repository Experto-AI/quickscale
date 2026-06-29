"""Refresh FORCE-RLS policies on all CRM enrolled tables (AF11 Phase 3).

Replaces every live FORCE-RLS policy with one built from the corrected
``apply_force_rls`` template (NULLIF-guarded).  The forward path drops
each existing policy then re-creates it from the shared template so the
NULLIF guard becomes active for every ENROLLED CRM table.

The reverse is intentionally a no-op (``migrations.RunPython.noop``) so
the legacy broken predicate (bare ``current_setting`` cast without
NULLIF) is never restored.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

# ---------------------------------------------------------------------------
# Policy names (reused from 0008 and 0009 — do not rename)
# ---------------------------------------------------------------------------
CRM_TAG_RLS_POLICY = "crm_tag_org_isolation"
CRM_COMPANY_RLS_POLICY = "crm_company_org_isolation"
CRM_CONTACT_RLS_POLICY = "crm_contact_org_isolation"
CRM_STAGE_RLS_POLICY = "crm_stage_org_isolation"
CRM_DEAL_RLS_POLICY = "crm_deal_org_isolation"
CRM_CONTACTNOTE_RLS_POLICY = "crm_contactnote_org_isolation"
CRM_DEALNOTE_RLS_POLICY = "crm_dealnote_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
CRM_TAG_TABLE = "quickscale_modules_crm_tag"
CRM_COMPANY_TABLE = "quickscale_modules_crm_company"
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_STAGE_TABLE = "quickscale_modules_crm_stage"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

# ---------------------------------------------------------------------------
# All (table, policy) pairs — the complete enrolled CRM set (7 tables)
# ---------------------------------------------------------------------------
_CRM_RLS_TARGETS = (
    (CRM_TAG_TABLE, CRM_TAG_RLS_POLICY),
    (CRM_COMPANY_TABLE, CRM_COMPANY_RLS_POLICY),
    (CRM_CONTACT_TABLE, CRM_CONTACT_RLS_POLICY),
    (CRM_STAGE_TABLE, CRM_STAGE_RLS_POLICY),
    (CRM_DEAL_TABLE, CRM_DEAL_RLS_POLICY),
    (CRM_CONTACTNOTE_TABLE, CRM_CONTACTNOTE_RLS_POLICY),
    (CRM_DEALNOTE_TABLE, CRM_DEALNOTE_RLS_POLICY),
)


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create them from the corrected template.

    The two-step sequence (revert → apply) ensures:
      1. The old bare ``current_setting`` policy is dropped first.
      2. The corrected NULLIF-guarded policy is created in its place.
    """
    del apps

    # Step 1: Drop every existing policy and disable RLS.
    revert_force_rls(schema_editor, _CRM_RLS_TARGETS)

    # Step 2: Re-enable RLS with the corrected NULLIF-guarded template.
    apply_force_rls(schema_editor, _CRM_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies with NULLIF guards on all CRM enrolled tables."""

    dependencies = [
        ("quickscale_modules_crm", "0009_add_note_organization_ownership"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
