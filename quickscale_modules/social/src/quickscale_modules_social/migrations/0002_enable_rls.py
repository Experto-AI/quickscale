"""Enable and FORCE PostgreSQL Row-Level Security on social tables.

T1.15 — Add DB-level RLS for social tables as a defense-in-depth layer
below the Django-level TenantManager.

Forward:
    1. ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY on both social
       tables so that RLS applies to every role including the table owner
       (Django connection).
    2. CREATE POLICY that uses ``current_setting('app.current_org_id', true)::uuid``
       for SELECT, INSERT, UPDATE, and DELETE.

Reverse:
    1. DROP the per-table policies.
    2. ALTER TABLE … NO FORCE ROW LEVEL SECURITY.
    3. ALTER TABLE … DISABLE ROW LEVEL SECURITY.

All admin reads/mutations on social tables must set ``app.current_org_id``
(and the ContextVar) inside a transaction before querying.  See
``admin.py`` ``_org_db_context()``.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

# ---------------------------------------------------------------------------
# Policy names
# ---------------------------------------------------------------------------
SOCIAL_LINK_RLS_POLICY = "social_link_org_isolation"
SOCIAL_EMBED_RLS_POLICY = "social_embed_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table for each model)
# ---------------------------------------------------------------------------
SOCIAL_LINK_TABLE = "quickscale_modules_social_sociallink"
SOCIAL_EMBED_TABLE = "quickscale_modules_social_socialembed"

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
    for table, policy in (
        (SOCIAL_LINK_TABLE, SOCIAL_LINK_RLS_POLICY),
        (SOCIAL_EMBED_TABLE, SOCIAL_EMBED_RLS_POLICY),
    ):
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
    for table, policy in (
        (SOCIAL_LINK_TABLE, SOCIAL_LINK_RLS_POLICY),
        (SOCIAL_EMBED_TABLE, SOCIAL_EMBED_RLS_POLICY),
    ):
        schema_editor.execute(
            _REVERSE_SQL.format(table=table, policy_name=policy),
        )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on social tables (T1.15)."""

    dependencies = [
        ("quickscale_modules_social", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            elidable=True,
        ),
    ]
