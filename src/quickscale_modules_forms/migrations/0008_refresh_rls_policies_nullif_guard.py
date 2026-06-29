"""Refresh FORCE-RLS policies on all Forms enrolled tables (AF11 Phase 3).

Replaces every live FORCE-RLS policy with one built from the corrected
``apply_force_rls`` template (NULLIF-guarded).  The forward path drops
each existing policy then re-creates it from the shared template so the
NULLIF guard becomes active for every ENROLLED Forms table.

The reverse is intentionally a no-op (``migrations.RunPython.noop``) so
the legacy broken predicate (bare ``current_setting`` cast without
NULLIF) is never restored.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

# ---------------------------------------------------------------------------
# Policy names (reused from 0006 and 0007 — do not rename)
# ---------------------------------------------------------------------------
FORMS_FORM_RLS_POLICY = "forms_form_org_isolation"
FORMS_FORMFIELD_RLS_POLICY = "forms_formfield_org_isolation"
FORMS_FORMSUBMISSION_RLS_POLICY = "forms_formsubmission_org_isolation"
FORMS_FORMFIELDVALUE_RLS_POLICY = "forms_formfieldvalue_org_isolation"

# ---------------------------------------------------------------------------
# Table names (explicit db_table from models.py Meta)
# ---------------------------------------------------------------------------
FORMS_FORM_TABLE = "quickscale_modules_forms_form"
FORMS_FORMFIELD_TABLE = "quickscale_modules_forms_formfield"
FORMS_FORMSUBMISSION_TABLE = "quickscale_modules_forms_formsubmission"
FORMS_FORMFIELDVALUE_TABLE = "quickscale_modules_forms_formfieldvalue"

# ---------------------------------------------------------------------------
# All (table, policy) pairs — the complete enrolled Forms set (4 tables)
# ---------------------------------------------------------------------------
_FORMS_RLS_TARGETS = (
    (FORMS_FORM_TABLE, FORMS_FORM_RLS_POLICY),
    (FORMS_FORMFIELD_TABLE, FORMS_FORMFIELD_RLS_POLICY),
    (FORMS_FORMSUBMISSION_TABLE, FORMS_FORMSUBMISSION_RLS_POLICY),
    (FORMS_FORMFIELDVALUE_TABLE, FORMS_FORMFIELDVALUE_RLS_POLICY),
)


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create them from the corrected template.

    The two-step sequence (revert → apply) ensures:
      1. The old bare ``current_setting`` policy is dropped first.
      2. The corrected NULLIF-guarded policy is created in its place.
    """
    del apps

    # Step 1: Drop every existing policy and disable RLS.
    revert_force_rls(schema_editor, _FORMS_RLS_TARGETS)

    # Step 2: Re-enable RLS with the corrected NULLIF-guarded template.
    apply_force_rls(schema_editor, _FORMS_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies with NULLIF guards on all Forms enrolled tables."""

    dependencies = [
        ("quickscale_modules_forms", "0007_new_organization_ownership"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
