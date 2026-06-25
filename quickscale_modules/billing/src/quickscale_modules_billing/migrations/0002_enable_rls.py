"""Enable and FORCE PostgreSQL Row-Level Security on Billing tables.

T1.16 — Add DB-level RLS for Billing tables as a defense-in-depth layer
below the Django-level TenantManager.

Applies to: CreditBalance, CreditTransaction, Subscription.
Does NOT apply to: Plan (no org FK), WebhookEvent (idempotency record, no org FK).

Forward:
    1. ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY on each
       org-owned billing table so that RLS applies to every role including
       the table owner (Django connection).
    2. CREATE POLICY that uses ``current_setting('app.current_org_id', true)::uuid``
       for SELECT, INSERT, UPDATE, and DELETE.

Reverse:
    1. DROP the per-table policies.
    2. ALTER TABLE … NO FORCE ROW LEVEL SECURITY.
    3. ALTER TABLE … DISABLE ROW LEVEL SECURITY.

Webhook / runtime paths (``handle_stripe_event``, ``_upsert_subscription_from_payload``,
``credit_user``) must establish org context via ``_billing_org_db_context(org)``
before querying these tables.  Org resolution uses the ``Organization`` table
(no RLS) and the ``stripe_customer_id`` column which is synced at checkout —
the ``Subscription`` fallback in ``_resolve_organization_by_customer_id`` is
only hit in data-inconsistency edge cases.

All admin reads/mutations on billing tables must set ``app.current_org_id``
(and the ContextVar) inside a transaction before querying.

This is a no-op on non-PostgreSQL databases (SQLite during tests).
"""

from typing import Any

from django.db import migrations

# ---------------------------------------------------------------------------
# Policy names
# ---------------------------------------------------------------------------
BILLING_CREDIT_BALANCE_RLS_POLICY = "billing_credit_balance_org_isolation"
BILLING_CREDIT_TRANSACTION_RLS_POLICY = "billing_credit_transaction_org_isolation"
BILLING_SUBSCRIPTION_RLS_POLICY = "billing_subscription_org_isolation"

# ---------------------------------------------------------------------------
# Table names (Django default db_table: appLabel_modelname)
# ---------------------------------------------------------------------------
BILLING_CREDIT_BALANCE_TABLE = "quickscale_modules_billing_creditbalance"
BILLING_CREDIT_TRANSACTION_TABLE = "quickscale_modules_billing_credittransaction"
BILLING_SUBSCRIPTION_TABLE = "quickscale_modules_billing_subscription"

# ---------------------------------------------------------------------------
# All (table, policy) pairs that receive RLS
# ---------------------------------------------------------------------------
_BILLING_RLS_TARGETS = (
    (BILLING_CREDIT_BALANCE_TABLE, BILLING_CREDIT_BALANCE_RLS_POLICY),
    (BILLING_CREDIT_TRANSACTION_TABLE, BILLING_CREDIT_TRANSACTION_RLS_POLICY),
    (BILLING_SUBSCRIPTION_TABLE, BILLING_SUBSCRIPTION_RLS_POLICY),
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
    for table, policy in _BILLING_RLS_TARGETS:
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
    for table, policy in _BILLING_RLS_TARGETS:
        schema_editor.execute(
            _REVERSE_SQL.format(table=table, policy_name=policy),
        )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration(migrations.Migration):
    """Enable PostgreSQL Row-Level Security on Billing tables (T1.16)."""

    dependencies = [
        ("quickscale_modules_billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward,
            reverse_code=_reverse,
            hints={"target_db": "default"},
        ),
    ]
