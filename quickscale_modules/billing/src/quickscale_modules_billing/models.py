"""Data models for the QuickScale billing module."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models, transaction

from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.tenancy import tenant_org_fk


CURRENT_SUBSCRIPTION_STATUSES = (
    "incomplete",
    "trialing",
    "active",
    "past_due",
    "unpaid",
    "paused",
)


def populated_value_q(field_name: str) -> models.Q:
    return models.Q(**{f"{field_name}__isnull": False}) & ~models.Q(**{field_name: ""})


def current_subscription_status_q(*, field_name: str = "status") -> models.Q:
    return models.Q(**{f"{field_name}__in": CURRENT_SUBSCRIPTION_STATUSES})


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
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CreditBalance(models.Model):
    """Current credit balance snapshot for a single organization."""

    organization = models.OneToOneField(
        "quickscale_modules_orgs.Organization",
        related_name="credit_balance",
        on_delete=models.PROTECT,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="credit_balance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        app_label = "quickscale_modules_billing"

    @classmethod
    def get_or_create_for_org(cls, organization: Any) -> tuple["CreditBalance", bool]:
        balance, created = cls.objects.get_or_create(
            organization=organization,
            defaults={"balance": 0},
        )

        if transaction.get_connection().in_atomic_block:
            return cls.objects.select_for_update().get(pk=balance.pk), created

        return cls.objects.get(pk=balance.pk), created

    def __str__(self) -> str:
        return f"{self.organization} ({self.balance} credits)"


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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    organization = tenant_org_fk(
        related_name="credit_transactions",
    )

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)
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
        actor = self.user or self.organization or "Unknown actor"
        return f"{actor} {self.transaction_type} {self.amount}"


class SubscriptionQuerySet(models.QuerySet["Subscription"]):
    """Query helpers for subscription state lookups."""

    def current(self) -> "SubscriptionQuerySet":
        """Return only rows that represent current subscription state."""

        return self.filter(current_subscription_status_q())


class Subscription(models.Model):
    """Local snapshot of a user's recurring billing state."""

    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete expired"
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"
        PAUSED = "paused", "Paused"

    CURRENT_STATUSES = CURRENT_SUBSCRIPTION_STATUSES

    organization = tenant_org_fk(
        related_name="subscriptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="billing_subscriptions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    plan = models.ForeignKey(
        Plan,
        related_name="subscriptions",
        on_delete=models.PROTECT,
    )
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.INCOMPLETE,
    )
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        app_label = "quickscale_modules_billing"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["stripe_subscription_id"],
                condition=populated_value_q("stripe_subscription_id"),
                name="quickscale_billing_unique_stripe_subscription_id_when_populated",
            ),
            models.UniqueConstraint(
                fields=["stripe_checkout_session_id"],
                condition=populated_value_q("stripe_checkout_session_id"),
                name="quickscale_billing_unique_stripe_checkout_session_id_present",
            ),
            models.UniqueConstraint(
                fields=["organization"],
                condition=current_subscription_status_q(),
                name="quickscale_billing_unique_current_subscription_per_organization",
            ),
        ]

    @classmethod
    def current_statuses(cls) -> tuple[str, ...]:
        """Return the local statuses that count as a current subscription."""

        return cls.CURRENT_STATUSES

    @classmethod
    def is_current_status(cls, status: str | None) -> bool:
        """Return whether the given local status is considered current."""

        normalized_status = (status or "").strip()
        return normalized_status in cls.current_statuses()

    @classmethod
    def current_status_q(cls, *, field_name: str = "status") -> models.Q:
        """Return a reusable predicate for current-subscription filtering."""

        return current_subscription_status_q(field_name=field_name)

    def __str__(self) -> str:
        return f"{self.organization} / {self.plan.slug} ({self.status})"


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
