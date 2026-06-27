"""Enable and FORCE PostgreSQL Row-Level Security on Billing tables.

T1.16 — Add DB-level RLS for Billing tables as a defense-in-depth layer
below the Django-level TenantManager.

Applies to: CreditBalance, CreditTransaction, Subscription.
Does NOT apply to: Plan (no org FK), WebhookEvent (idempotency record, no org FK).

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


def _forward(apps: Any, schema_editor: Any) -> None:
    apply_force_rls(schema_editor, _BILLING_RLS_TARGETS)


def _reverse(apps: Any, schema_editor: Any) -> None:
    revert_force_rls(schema_editor, _BILLING_RLS_TARGETS)


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
