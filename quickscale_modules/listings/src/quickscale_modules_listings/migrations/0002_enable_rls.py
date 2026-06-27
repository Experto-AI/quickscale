"""Enable and FORCE PostgreSQL Row-Level Security on Listings tables.

T1.14 — Add DB-level RLS for Listings tables as a defense-in-depth layer
below the Django-level TenantManager.

AbstractListing is abstract and generates no DB table.  The concrete
``Listing`` model (which extends AbstractListing) is the only table that
receives an RLS policy here.  Projects that extend AbstractListing to
create their own concrete listing types must add their own RLS migration.

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
LISTINGS_LISTING_RLS_POLICY = "listings_listing_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
LISTINGS_LISTING_TABLE = "quickscale_modules_listings_listing"

# ---------------------------------------------------------------------------
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_LISTINGS_RLS_TARGETS = ((LISTINGS_LISTING_TABLE, LISTINGS_LISTING_RLS_POLICY),)


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on Listing table (T1.14)."""

    dependencies = [
        ("quickscale_modules_listings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            hints={"target_db": "default"},
        ),
    ]
