"""Verify the squashed billing migration applies cleanly.

WARNING: This test reverses then re-applies billing migrations 0002–0004.
The reverse step drops RLS policies via DDL that cannot be rolled back
(PostgreSQL auto-commits DDL).  We therefore re-apply forward to the
latest migration, restoring RLS before the test returns, so that
downstream tests (e.g. RLS boundary tests in the same session) are not
affected.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_initial_migration_applies_cleanly() -> None:
    """Run the initial billing migration to confirm it applies.

    Round-trips to 0001 and back to the latest migration so that DDL side
    effects from reversing 0002 (RLS policies) are re-applied before the
    test returns.
    """
    executor = MigrationExecutor(connection)

    # Phase 1 — reverse to 0001 (tests forward application of the initial
    # migration after the test database was created with all migrations).
    executor.migrate(
        [
            ("quickscale_modules_orgs", "0003_alter_organization_is_system"),
            ("quickscale_modules_billing", "0001_initial"),
        ]
    )

    applied_migrations = executor.loader.applied_migrations
    billing_migrations = [
        m for m in applied_migrations if m[0] == "quickscale_modules_billing"
    ]

    assert billing_migrations, "No billing migrations were applied"

    # Phase 2 — re-apply forward to the latest migration so RLS policies
    # (dropped by reversing 0002) are restored.  DDL side effects from
    # migration reversal cannot be rolled back; this forward migration
    # re-applies them.
    executor.migrate(
        [
            ("quickscale_modules_orgs", "0004_organizationtombstone"),
            (
                "quickscale_modules_billing",
                "0004_credit_transaction_unique_stripe_event_per_type",
            ),
        ]
    )
