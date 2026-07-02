"""Add partial unique constraint on (stripe_event_id, transaction_type) for DB-enforced idempotency.

This is the DB-level backstop for SA12.1.  When a concurrent ``credit_user`` call
slips past the procedural ``_find_existing_credit_transaction`` read, the partial
unique constraint raises an ``IntegrityError`` that ``credit_user`` now catches
and recovers from by returning the existing row.

**Pre-flight (RunPython)**: clears ``stripe_event_id`` on older duplicate rows
so that ``AddConstraint`` does not fail on legacy data that already violates the
new uniqueness contract.  For each ``(stripe_event_id, transaction_type)`` group,
only the row with the highest ``id`` is kept; the others have their
``stripe_event_id`` set to ``''`` (empty string), which is excluded by the
partial condition.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations, models

from quickscale_modules_billing.models import populated_value_q


def _deduplicate_credit_transaction_stripe_event_ids(
    apps: Any,
    schema_editor: Any,
) -> None:
    """Clear ``stripe_event_id`` on older duplicates so AddConstraint can succeed.

    For each ``(stripe_event_id, transaction_type)`` group where
    ``stripe_event_id`` is populated, only the row with the highest ``id``
    retains its ``stripe_event_id``.  All other rows in the group get
    ``stripe_event_id = ''`` (which the partial unique index ignores).

    The reverse is intentionally a no-op — we cannot restore data that was
    semantically duplicate.
    """
    CreditTransaction = apps.get_model(
        "quickscale_modules_billing", "CreditTransaction"
    )
    table_name = CreditTransaction._meta.db_table

    schema_editor.execute(
        f"""
        UPDATE {table_name}
        SET stripe_event_id = ''
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY stripe_event_id, transaction_type
                    ORDER BY id DESC
                ) AS rn
                FROM {table_name}
                WHERE stripe_event_id IS NOT NULL AND stripe_event_id <> ''
            ) AS ranked
            WHERE rn > 1
        );
        """
    )


class Migration(migrations.Migration):
    """Add partial unique constraint on CreditTransaction for stripe_event_id + transaction_type."""

    dependencies = [
        ("quickscale_modules_billing", "0003_refresh_rls_policies_nullif_guard"),
    ]

    operations = [
        migrations.RunPython(
            code=_deduplicate_credit_transaction_stripe_event_ids,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
        migrations.AddConstraint(
            model_name="credittransaction",
            constraint=models.UniqueConstraint(
                fields=["stripe_event_id", "transaction_type"],
                condition=populated_value_q("stripe_event_id"),
                name="quickscale_billing_unique_stripe_event_id_per_type",
            ),
        ),
    ]
