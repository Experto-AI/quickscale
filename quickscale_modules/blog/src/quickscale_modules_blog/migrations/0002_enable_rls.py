"""Enable and FORCE PostgreSQL Row-Level Security on Blog tables.

T1.12 — Add DB-level RLS for Blog tables as a defense-in-depth layer
below the Django-level TenantManager.

Forward:
    1. ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY on every
       org-owned Blog table so that RLS applies to every role including
       the table owner (Django connection).
    2. CREATE POLICY that uses ``current_setting('app.current_org_id', true)::uuid``
       for SELECT, INSERT, UPDATE, and DELETE.

Reverse:
    1. DROP the per-table policies.
    2. ALTER TABLE … NO FORCE ROW LEVEL SECURITY.
    3. ALTER TABLE … DISABLE ROW LEVEL SECURITY.

AuthorProfile links to a User (not an org), so it does not receive an RLS
policy here — its visibility is controlled by the org-scoped Post FK.

All admin reads/mutations on Blog tables must set ``app.current_org_id``
(and the ContextVar) inside a transaction before querying.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

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
    for table, policy in _BLOG_RLS_TARGETS:
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
    for table, policy in _BLOG_RLS_TARGETS:
        schema_editor.execute(
            _REVERSE_SQL.format(table=table, policy_name=policy),
        )


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
