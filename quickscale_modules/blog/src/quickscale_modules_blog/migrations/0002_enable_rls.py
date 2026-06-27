"""Enable and FORCE PostgreSQL Row-Level Security on Blog tables.

T1.12 — Add DB-level RLS for Blog tables as a defense-in-depth layer
below the Django-level TenantManager.

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
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_BLOG_RLS_TARGETS = (
    (BLOG_CATEGORY_TABLE, BLOG_CATEGORY_RLS_POLICY),
    (BLOG_TAG_TABLE, BLOG_TAG_RLS_POLICY),
    (BLOG_MEDIA_ASSET_TABLE, BLOG_MEDIA_ASSET_RLS_POLICY),
    (BLOG_POST_TABLE, BLOG_POST_RLS_POLICY),
)


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _BLOG_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _BLOG_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on Blog tables (T1.12)."""

    dependencies = [
        ("quickscale_modules_blog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            hints={"target_db": "default"},
        ),
    ]
