"""Admin configuration for the QuickScale billing module."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import admin
from django.http import HttpRequest, HttpResponse

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)


class ReadOnlyAdminMixin:
    """Shared read-only admin behavior for operational billing models."""

    _extra_readonly_fields: list[str] = []

    def has_add_permission(self, request: HttpRequest) -> bool:
        del request
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Any | None = None,
    ) -> bool:
        del request, obj
        return False

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: Any | None = None,
    ) -> list[str]:
        del request, obj
        model_fields = [field.name for field in self.model._meta.fields]
        return [*model_fields, *self._extra_readonly_fields]

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        merged_context = {
            **(extra_context or {}),
            "show_save": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": False,
            "show_delete": False,
        }
        return cast(Any, super()).change_view(
            request,
            object_id,
            form_url=form_url,
            extra_context=merged_context,
        )


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Full CRUD admin for plan metadata."""

    list_display = [
        "name",
        "slug",
        "billing_interval",
        "credits_per_period",
        "price_cents",
        "currency",
        "is_active",
    ]
    list_filter = ["billing_interval", "currency", "is_active"]
    search_fields = ["name", "slug", "stripe_price_id"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(CreditBalance)
class CreditBalanceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Read-only admin for per-user balance snapshots."""

    list_display = ["user", "balance", "updated_at"]
    list_select_related = ["user"]


@admin.register(CreditTransaction)
class CreditTransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Read-only admin for credit transaction history."""

    list_display = [
        "user",
        "transaction_type",
        "amount",
        "balance_after",
        "stripe_object_id",
        "created_at",
    ]
    list_filter = ["transaction_type", "created_at"]
    list_select_related = ["user"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Editable admin surface for local subscription snapshots."""

    list_display = [
        "user",
        "plan",
        "status",
        "stripe_subscription_id",
        "current_period_end",
    ]
    list_filter = ["status", "plan"]
    list_select_related = ["user", "plan"]
    search_fields = ["stripe_subscription_id", "stripe_customer_id"]


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Read-only admin for webhook idempotency records."""

    list_display = ["stripe_event_id", "event_type", "processed", "created_at"]
    list_filter = ["processed", "event_type", "created_at"]
