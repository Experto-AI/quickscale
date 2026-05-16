"""DRF serializers for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from quickscale_modules_billing.models import CreditTransaction, Plan


class CreateCheckoutSessionSerializer(serializers.Serializer):
    """Validate a one-time credit purchase request."""

    plan_slug = serializers.SlugField()

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            unexpected_fields = sorted(set(data) - {"plan_slug"})
            if unexpected_fields:
                raise serializers.ValidationError(
                    {
                        field_name: ["This field is not allowed."]
                        for field_name in unexpected_fields
                    }
                )

        return super().to_internal_value(data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        plan_slug = str(attrs.get("plan_slug") or "").strip()
        plan = Plan.objects.filter(slug=plan_slug).order_by("pk").first()
        if plan is None:
            raise serializers.ValidationError({"plan_slug": "Unknown billing plan."})
        if not plan.is_active:
            raise serializers.ValidationError(
                {"plan_slug": "Billing plan is not active."}
            )
        if plan.billing_interval != Plan.BillingInterval.ONE_TIME:
            raise serializers.ValidationError(
                {"plan_slug": "Billing plan does not support one-time purchases."}
            )

        attrs["plan"] = plan
        return attrs


class CreditBalanceSerializer(serializers.Serializer):
    """Serialize the current credit balance snapshot."""

    balance = serializers.IntegerField()
    updated_at = serializers.DateTimeField(allow_null=True)


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
    "CreditBalanceSerializer",
    "CreditTransactionSerializer",
]
