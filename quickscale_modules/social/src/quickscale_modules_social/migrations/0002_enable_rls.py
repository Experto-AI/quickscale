"""Enable and FORCE PostgreSQL Row-Level Security on social tables.

T1.15 — Add DB-level RLS for social tables as a defense-in-depth layer
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
SOCIAL_LINK_RLS_POLICY = "social_link_org_isolation"
SOCIAL_EMBED_RLS_POLICY = "social_embed_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table for each model)
# ---------------------------------------------------------------------------
SOCIAL_LINK_TABLE = "quickscale_modules_social_sociallink"
SOCIAL_EMBED_TABLE = "quickscale_modules_social_socialembed"

# ---------------------------------------------------------------------------
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_SOCIAL_RLS_TARGETS = (
    (SOCIAL_LINK_TABLE, SOCIAL_LINK_RLS_POLICY),
    (SOCIAL_EMBED_TABLE, SOCIAL_EMBED_RLS_POLICY),
)


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _SOCIAL_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _SOCIAL_RLS_TARGETS)


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
