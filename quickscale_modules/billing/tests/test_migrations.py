"""Verify the squashed billing migration applies cleanly."""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_initial_migration_applies_cleanly() -> None:
    """Run the initial billing migration to confirm it applies."""
    executor = MigrationExecutor(connection)
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
