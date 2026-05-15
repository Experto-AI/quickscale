"""Data models for the QuickScale billing module."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models, transaction


class Plan(models.Model):
    """QuickScale-owned plan metadata that points at a Stripe price."""

    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        ONE_TIME = "one_time", "One-time"

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    stripe_price_id = models.CharField(max_length=255, unique=True)
    credits_per_period = models.PositiveIntegerField()
    price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="usd")
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CreditBalance(models.Model):
    """Current credit balance snapshot for a single user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="credit_balance",
        on_delete=models.CASCADE,
    )
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_billing"

    @classmethod
    def get_or_create_for_user(cls, user: Any) -> tuple["CreditBalance", bool]:
        """Return the user's balance row, locking it when called inside a transaction."""

        balance, created = cls.objects.get_or_create(
            user=user,
            defaults={"balance": 0},
        )

        if transaction.get_connection().in_atomic_block:
            return cls.objects.select_for_update().get(pk=balance.pk), created

        return cls.objects.get(pk=balance.pk), created

    def __str__(self) -> str:
        return f"{self.user} ({self.balance} credits)"


class CreditTransaction(models.Model):
    """Immutable audit log entry for a credit balance mutation."""

    class TransactionType(models.TextChoices):
        PLAN = "plan", "Plan"
        PURCHASE = "purchase", "Purchase"
        USAGE = "usage", "Usage"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Adjustment"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="credit_transactions",
        on_delete=models.CASCADE,
    )
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    stripe_event_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_object_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_reference_data = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    balance_after = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} {self.transaction_type} {self.amount}"


class Subscription(models.Model):
    """Local snapshot of a user's recurring billing state."""

    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="billing_subscriptions",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(
        Plan,
        related_name="subscriptions",
        on_delete=models.PROTECT,
    )
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    stripe_customer_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.INCOMPLETE,
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.user} / {self.plan.slug} ({self.status})"


class WebhookEvent(models.Model):
    """Transport-level idempotency record for future Stripe webhook handling."""

    stripe_event_id = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["stripe_event_id"],
                name="quickscale_billing_unique_stripe_event_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.stripe_event_id})"
