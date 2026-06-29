"""Refresh FORCE-RLS policies on all Listings enrolled tables (AF11 Phase 3).

Replaces the live FORCE-RLS policy with one built from the corrected
``apply_force_rls`` template (NULLIF-guarded).  The forward path drops
the existing policy then re-creates it from the shared template so the
NULLIF guard becomes active for the Listing table.

The reverse is intentionally a no-op (``migrations.RunPython.noop``) so
the legacy broken predicate (bare ``current_setting`` cast without
NULLIF) is never restored.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

# ---------------------------------------------------------------------------
# Policy names (reused from 0002 — do not rename)
# ---------------------------------------------------------------------------
LISTINGS_LISTING_RLS_POLICY = "listings_listing_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
LISTINGS_LISTING_TABLE = "quickscale_modules_listings_listing"

# ---------------------------------------------------------------------------
# All (table, policy) pairs — the complete enrolled Listings set (1 table)
# ---------------------------------------------------------------------------
_LISTINGS_RLS_TARGETS = ((LISTINGS_LISTING_TABLE, LISTINGS_LISTING_RLS_POLICY),)


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policy then re-create it from the corrected template.

    The two-step sequence (revert → apply) ensures:
      1. The old bare ``current_setting`` policy is dropped first.
      2. The corrected NULLIF-guarded policy is created in its place.
    """
    del apps

    # Step 1: Drop the existing policy and disable RLS.
    revert_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)

    # Step 2: Re-enable RLS with the corrected NULLIF-guarded template.
    apply_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies with NULLIF guards on the Listing table."""

    dependencies = [
        ("quickscale_modules_listings", "0002_enable_rls"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
