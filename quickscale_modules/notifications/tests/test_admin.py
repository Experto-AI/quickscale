"""Tests for notifications module admin configuration."""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib import admin
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.urls import reverse

from quickscale_modules_notifications.admin import (
    NotificationMessageAdmin,
    NotificationSettingsAdmin,
)
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationMessage,
    NotificationSettings,
)


def _settings_admin() -> NotificationSettingsAdmin:
    return cast(NotificationSettingsAdmin, admin.site._registry[NotificationSettings])


def _message_admin() -> NotificationMessageAdmin:
    return cast(NotificationMessageAdmin, admin.site._registry[NotificationMessage])


@pytest.mark.django_db
class TestAdminRegistration:
    def test_models_are_registered(self) -> None:
        assert admin.site.is_registered(NotificationSettings)
        assert admin.site.is_registered(NotificationMessage)
        assert admin.site.is_registered(NotificationDelivery)


@pytest.mark.django_db
class TestNotificationSettingsAdmin:
    def test_has_add_permission_is_disabled(
        self,
        superuser,
    ) -> None:
        settings_admin = _settings_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        assert settings_admin.has_add_permission(request) is False

    def test_snapshot_fields_are_all_read_only(
        self,
        notification_settings_row,
        superuser,
    ) -> None:
        settings_admin = _settings_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        readonly_fields = settings_admin.get_readonly_fields(
            request,
            notification_settings_row,
        )
        model_field_names = [field.name for field in NotificationSettings._meta.fields]

        assert set(model_field_names).issubset(set(readonly_fields))
        assert "authoritative_source_notice" in readonly_fields
        assert "secret_storage_notice" in readonly_fields
        assert "webhook_notice" in readonly_fields

    def test_change_view_is_read_only_and_explains_authoritative_source(
        self,
        admin_client: Client,
        notification_settings_row,
    ) -> None:
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_notifications_notificationsettings_change",
                args=[notification_settings_row.pk],
            )
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "quickscale apply" in content
        assert "operator visibility only" in content
        assert 'name="_save"' not in content
        assert 'class="deletelink"' not in content


@pytest.mark.django_db
class TestNotificationMessageAdmin:
    def test_recipient_count_uses_delivery_rows(
        self,
        queued_message,
        superuser,
    ) -> None:
        message_admin = _message_admin()
        request: HttpRequest = RequestFactory().get("/admin/")
        request.user = superuser

        del request
        assert message_admin.recipient_count(queued_message) == 2
