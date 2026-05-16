"""DRF serializers for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from quickscale_modules_billing.models import CreditTransaction, Plan, Subscription

_RECURRING_BILLING_INTERVALS = (
    Plan.BillingInterval.MONTHLY,
    Plan.BillingInterval.YEARLY,
)


def _reject_unexpected_fields(data: Any, *, allowed_fields: set[str]) -> None:
    if not isinstance(data, Mapping):
        return

    unexpected_fields = sorted(set(data) - allowed_fields)
    if unexpected_fields:
        raise serializers.ValidationError(
            {
                field_name: ["This field is not allowed."]
                for field_name in unexpected_fields
            }
        )


def _resolve_active_plan(plan_slug: Any) -> Plan:
    normalized_plan_slug = str(plan_slug or "").strip()
    plan = Plan.objects.filter(slug=normalized_plan_slug).order_by("pk").first()
    if plan is None:
        raise serializers.ValidationError({"plan_slug": "Unknown billing plan."})
    if not plan.is_active:
        raise serializers.ValidationError({"plan_slug": "Billing plan is not active."})
    return plan


class PlanSerializer(serializers.ModelSerializer):
    """Serialize the public recurring plan catalog contract."""

    class Meta:
        model = Plan
        fields = [
            "name",
            "slug",
            "credits_per_period",
            "price_cents",
            "currency",
            "billing_interval",
        ]
        read_only_fields = fields


class CreateCheckoutSessionSerializer(serializers.Serializer):
    """Validate a one-time credit purchase request."""

    plan_slug = serializers.SlugField()

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        _reject_unexpected_fields(data, allowed_fields={"plan_slug"})
        return super().to_internal_value(data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        plan = _resolve_active_plan(attrs.get("plan_slug"))
        if plan.billing_interval != Plan.BillingInterval.ONE_TIME:
            raise serializers.ValidationError(
                {"plan_slug": "Billing plan does not support one-time purchases."}
            )

        attrs["plan"] = plan
        return attrs


class CreateSubscriptionCheckoutSerializer(serializers.Serializer):
    """Validate a recurring subscription checkout request."""

    plan_slug = serializers.SlugField()

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        _reject_unexpected_fields(data, allowed_fields={"plan_slug"})
        return super().to_internal_value(data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        plan = _resolve_active_plan(attrs.get("plan_slug"))
        if plan.billing_interval not in _RECURRING_BILLING_INTERVALS:
            raise serializers.ValidationError(
                {"plan_slug": "Billing plan does not support recurring subscriptions."}
            )

        attrs["plan"] = plan
        return attrs


class CreditBalanceSerializer(serializers.Serializer):
    """Serialize the current credit balance snapshot."""

    balance = serializers.IntegerField()
    updated_at = serializers.DateTimeField(allow_null=True)


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serialize the authenticated user's current recurring subscription."""

    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "status",
            "checkout_expires_at",
            "current_period_start",
            "current_period_end",
        ]
        read_only_fields = fields


class CreditTransactionSerializer(serializers.ModelSerializer):
    """Serialize a credit transaction for user-facing purchase history."""

    class Meta:
        model = CreditTransaction
        fields = [
            "id",
            "amount",
            "transaction_type",
            "description",
            "balance_after",
            "created_at",
        ]
        read_only_fields = fields


__all__ = [
    "CreateCheckoutSessionSerializer",
    "CreateSubscriptionCheckoutSerializer",
    "CreditBalanceSerializer",
    "CreditTransactionSerializer",
    "PlanSerializer",
    "SubscriptionSerializer",
]
