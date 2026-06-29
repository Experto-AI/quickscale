"""Refresh FORCE-RLS policies on all Blog enrolled tables (AF11 Phase 3).

Replaces every live FORCE-RLS policy with one built from the corrected
``apply_force_rls`` template (NULLIF-guarded).  The forward path drops
each existing policy then re-creates it from the shared template so the
NULLIF guard becomes active for every ENROLLED Blog table.

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
BLOG_CATEGORY_RLS_POLICY = "blog_category_org_isolation"
BLOG_TAG_RLS_POLICY = "blog_tag_org_isolation"
BLOG_MEDIA_ASSET_RLS_POLICY = "blog_media_asset_org_isolation"
BLOG_POST_RLS_POLICY = "blog_post_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
BLOG_CATEGORY_TABLE = "quickscale_modules_blog_category"
BLOG_TAG_TABLE = "quickscale_modules_blog_tag"
BLOG_MEDIA_ASSET_TABLE = "quickscale_modules_blog_blogmediaasset"
BLOG_POST_TABLE = "quickscale_modules_blog_post"

# ---------------------------------------------------------------------------
# All (table, policy) pairs — the complete enrolled Blog set (4 tables)
# ---------------------------------------------------------------------------
_BLOG_RLS_TARGETS = (
    (BLOG_CATEGORY_TABLE, BLOG_CATEGORY_RLS_POLICY),
    (BLOG_TAG_TABLE, BLOG_TAG_RLS_POLICY),
    (BLOG_MEDIA_ASSET_TABLE, BLOG_MEDIA_ASSET_RLS_POLICY),
    (BLOG_POST_TABLE, BLOG_POST_RLS_POLICY),
)


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create them from the corrected template.

    The two-step sequence (revert → apply) ensures:
      1. The old bare ``current_setting`` policy is dropped first.
      2. The corrected NULLIF-guarded policy is created in its place.
    """
    del apps

    # Step 1: Drop every existing policy and disable RLS.
    revert_force_rls(schema_editor, _BLOG_RLS_TARGETS)

    # Step 2: Re-enable RLS with the corrected NULLIF-guarded template.
    apply_force_rls(schema_editor, _BLOG_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies with NULLIF guards on all Blog enrolled tables."""

    dependencies = [
        ("quickscale_modules_blog", "0002_enable_rls"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
