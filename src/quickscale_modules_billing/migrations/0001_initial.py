"""Initial migration for the QuickScale Billing module."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.conf import settings
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

BILLING_CREDIT_BALANCE_RLS_POLICY = "billing_credit_balance_org_isolation"
BILLING_CREDIT_TRANSACTION_RLS_POLICY = "billing_credit_transaction_org_isolation"
BILLING_PURCHASE_CHECKOUT_RLS_POLICY = "billing_purchase_checkout_org_isolation"
BILLING_SUBSCRIPTION_RLS_POLICY = "billing_subscription_org_isolation"
BILLING_CREDIT_BALANCE_TABLE = "quickscale_billing_creditbalance"
BILLING_CREDIT_TRANSACTION_TABLE = "quickscale_billing_credittransaction"
BILLING_PURCHASE_CHECKOUT_TABLE = "quickscale_billing_purchasecheckout"
BILLING_SUBSCRIPTION_TABLE = "quickscale_billing_subscription"
_BILLING_RLS_TARGETS = (
    (BILLING_CREDIT_BALANCE_TABLE, BILLING_CREDIT_BALANCE_RLS_POLICY),
    (BILLING_CREDIT_TRANSACTION_TABLE, BILLING_CREDIT_TRANSACTION_RLS_POLICY),
    (BILLING_PURCHASE_CHECKOUT_TABLE, BILLING_PURCHASE_CHECKOUT_RLS_POLICY),
    (BILLING_SUBSCRIPTION_TABLE, BILLING_SUBSCRIPTION_RLS_POLICY),
)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the NULLIF-guarded template."""
    del apps
    revert_force_rls(schema_editor, _BILLING_RLS_TARGETS)
    apply_force_rls(schema_editor, _BILLING_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(unique=True)),
                ("stripe_price_id", models.CharField(max_length=255, unique=True)),
                ("credits_per_period", models.PositiveIntegerField()),
                ("price_cents", models.PositiveIntegerField()),
                ("currency", models.CharField(default="usd", max_length=3)),
                (
                    "billing_interval",
                    models.CharField(
                        choices=[
                            ("monthly", "Monthly"),
                            ("yearly", "Yearly"),
                            ("one_time", "One-time"),
                        ],
                        default="monthly",
                        max_length=20,
                    ),
                ),
                ("features", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="CreditBalance",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("balance", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quickscale_billing_credit_balance",
                        to="quickscale_orgs.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quickscale_billing_credit_balances",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"base_manager_name": "all_objects"},
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("stripe_event_id", models.CharField(db_index=True, max_length=255)),
                ("event_type", models.CharField(max_length=100)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("processing_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("stripe_event_id",),
                        name="quickscale_billing_webhookevent_stripe_event_id_unique",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CreditTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("amount", models.IntegerField()),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("plan", "Plan"),
                            ("purchase", "Purchase"),
                            ("usage", "Usage"),
                            ("refund", "Refund"),
                            ("adjustment", "Adjustment"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "stripe_event_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "stripe_object_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                ("stripe_reference_data", models.JSONField(blank=True, default=dict)),
                ("description", models.TextField(blank=True)),
                ("balance_after", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quickscale_billing_credit_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "all_objects",
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("stripe_event_id__isnull", False),
                            models.Q(("stripe_event_id", ""), _negated=True),
                        ),
                        fields=("stripe_event_id", "transaction_type"),
                        name="quickscale_billing_credittransaction_stripe_event_id_unique",
                    )
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseCheckout",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "stripe_checkout_session_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("preparing", "Preparing"),
                            ("open", "Open"),
                            ("completed", "Completed"),
                            ("expired", "Expired"),
                        ],
                        default="preparing",
                        max_length=20,
                    ),
                ),
                ("checkout_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_checkouts",
                        to="quickscale_billing.plan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quickscale_billing_purchase_checkouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "stripe_subscription_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "stripe_customer_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=255, null=True
                    ),
                ),
                (
                    "stripe_checkout_session_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("incomplete", "Incomplete"),
                            ("incomplete_expired", "Incomplete expired"),
                            ("trialing", "Trialing"),
                            ("active", "Active"),
                            ("past_due", "Past due"),
                            ("canceled", "Canceled"),
                            ("unpaid", "Unpaid"),
                            ("paused", "Paused"),
                        ],
                        default="incomplete",
                        max_length=32,
                    ),
                ),
                ("checkout_expires_at", models.DateTimeField(blank=True, null=True)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quickscale_billing_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="quickscale_billing.plan",
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
                "base_manager_name": "all_objects",
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("stripe_subscription_id__isnull", False),
                            models.Q(("stripe_subscription_id", ""), _negated=True),
                        ),
                        fields=("stripe_subscription_id",),
                        name="quickscale_billing_subscription_stripe_subscription_id_unique",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("stripe_checkout_session_id__isnull", False),
                            models.Q(("stripe_checkout_session_id", ""), _negated=True),
                        ),
                        fields=("stripe_checkout_session_id",),
                        name="quickscale_billing_subscription_stripe_checkout_unique",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            (
                                "status__in",
                                (
                                    "incomplete",
                                    "trialing",
                                    "active",
                                    "past_due",
                                    "unpaid",
                                    "paused",
                                ),
                            )
                        ),
                        fields=("organization",),
                        name="quickscale_billing_subscription_current_per_organization_unique",
                    ),
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
