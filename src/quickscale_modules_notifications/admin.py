"""Admin configuration for the QuickScale notifications module."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import admin
from django.http import HttpRequest, HttpResponse

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
    NotificationSettings,
)
from quickscale_modules_notifications.services import ensure_default_settings


class ReadOnlyAdminMixin:
    """Shared read-only admin behavior for operational snapshot models."""

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


class NotificationDeliveryInline(admin.TabularInline):
    """Read-only inline for recipient delivery records."""

    model = NotificationDelivery
    extra = 0
    can_delete = False
    show_change_link = True
    readonly_fields = [
        "recipient_email",
        "provider_message_id",
        "status",
        "last_event_type",
        "failure_reason",
        "retry_count",
        "dispatched_at",
        "last_event_at",
        "delivered_at",
        "failed_at",
        "created_at",
        "updated_at",
    ]


class NotificationDeliveryEventInline(admin.TabularInline):
    """Read-only inline for provider event history records."""

    model = NotificationDeliveryEvent
    extra = 0
    can_delete = False
    readonly_fields = [
        "provider_event_id",
        "idempotency_key",
        "event_type",
        "provider_message_id",
        "status_after",
        "payload_json",
        "occurred_at",
        "received_at",
    ]


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Read-only admin view of the effective notification settings snapshot."""

    _extra_readonly_fields = [
        "authoritative_source_notice",
        "secret_storage_notice",
        "webhook_notice",
    ]

    list_display = [
        "key",
        "provider_name",
        "sender_email",
        "email_backend",
        "updated_at",
    ]
    fieldsets = [
        (
            "Applied settings snapshot",
            {
                "fields": [
                    "authoritative_source_notice",
                    "enabled",
                    "provider_name",
                    "email_backend",
                    "sender_name",
                    "sender_email",
                    "reply_to_email",
                    "resend_domain",
                ],
                "description": (
                    "Runtime notification behavior is controlled by generated settings "
                    "and environment variables. This admin page mirrors the effective "
                    "snapshot for operator visibility only."
                ),
            },
        ),
        (
            "Secret-free environment wiring",
            {
                "fields": [
                    "resend_api_key_env_var",
                    "webhook_secret_env_var",
                    "secret_storage_notice",
                ]
            },
        ),
        (
            "Provider-visible metadata policy",
            {
                "fields": [
                    "default_tags",
                    "allowed_tags",
                    "webhook_ttl_seconds",
                    "webhook_notice",
                ]
            },
        ),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        ensure_default_settings()
        return super().changelist_view(request, extra_context)

    @admin.display(description="Authoritative source")
    def authoritative_source_notice(self, obj: NotificationSettings) -> str:
        del obj
        return (
            "Edit notification settings in quickscale.yml and re-run 'quickscale apply'. "
            "Generated Django settings and environment variables remain authoritative, "
            "and this admin record is a read-only snapshot of those values."
        )

    @admin.display(description="Secret storage")
    def secret_storage_notice(self, obj: NotificationSettings) -> str:
        del obj
        return (
            "Only environment-variable names are stored here. Raw Resend API keys and "
            "webhook secrets are never persisted in the database."
        )

    @admin.display(description="Webhook guidance")
    def webhook_notice(self, obj: NotificationSettings) -> str:
        del obj
        return (
            "Webhook requests must include a valid shared-secret signature and are "
            "processed idempotently to avoid duplicate event corruption."
        )


@admin.register(NotificationMessage)
class NotificationMessageAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Operator-facing notification message history."""

    list_display = [
        "template_key",
        "status",
        "recipient_count",
        "created_at",
        "dispatched_at",
        "last_event_at",
    ]
    list_filter = ["status", "provider_name", "created_at"]
    search_fields = [
        "template_key",
        "subject",
        "deliveries__recipient_email",
        "deliveries__provider_message_id",
    ]
    readonly_fields = [
        "template_key",
        "subject",
        "from_email",
        "reply_to_email",
        "rendered_text",
        "rendered_html",
        "context_json",
        "provider_name",
        "tags_json",
        "metadata_json",
        "status",
        "last_error",
        "dispatched_at",
        "last_event_at",
        "created_at",
        "updated_at",
        "recipient_count",
    ]
    fieldsets = [
        (
            "Message",
            {
                "fields": [
                    "template_key",
                    "subject",
                    "status",
                    "recipient_count",
                    "provider_name",
                ]
            },
        ),
        (
            "Rendered content",
            {
                "fields": [
                    "from_email",
                    "reply_to_email",
                    "rendered_text",
                    "rendered_html",
                    "context_json",
                ]
            },
        ),
        (
            "Provider-visible data",
            {"fields": ["tags_json", "metadata_json", "last_error"]},
        ),
        (
            "Timestamps",
            {"fields": ["dispatched_at", "last_event_at", "created_at", "updated_at"]},
        ),
    ]
    inlines = [NotificationDeliveryInline]

    @admin.display(description="Recipients")
    def recipient_count(self, obj: NotificationMessage) -> int:
        return obj.deliveries.count()


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Read-only recipient delivery audit surface."""

    list_display = [
        "recipient_email",
        "message",
        "status",
        "provider_message_id",
        "last_event_type",
        "retry_count",
        "last_event_at",
    ]
    list_filter = ["status", "last_event_type", "created_at"]
    search_fields = ["recipient_email", "provider_message_id", "message__template_key"]
    readonly_fields = [
        "message",
        "recipient_email",
        "provider_message_id",
        "status",
        "last_event_type",
        "failure_reason",
        "retry_count",
        "dispatched_at",
        "last_event_at",
        "delivered_at",
        "failed_at",
        "created_at",
        "updated_at",
    ]
    inlines = [NotificationDeliveryEventInline]
