"""Shared pytest fixtures for the QuickScale notifications module."""

from __future__ import annotations

import os

import django
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

# The bypass_rls marker and its collection-time opt-in come from core's
# conftest plugin (decisions rule 18); this suite only adds its reuse-db
# wrapper on top, so every module suite shares one copy of the hook.
from quickscale_core.testing.pytest_plugin import (  # noqa: F401
    pytest_collection_modifyitems,
    pytest_configure as shared_pytest_configure,
)
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationMessage,
)
from quickscale_modules_notifications.services import ensure_default_settings

# NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The shared collection hook deselects bypass_rls-marked tests unless the env var
# is exactly 1. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# This runs before django.setup() below — use a NOBYPASSRLS DB role.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
os.environ.setdefault("RESEND_API_KEY", "test-resend-api-key")
os.environ.setdefault(
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
    "whsec_YWFhYWFhYWFhYWFhYWFhYQ==",
)
django.setup()


@pytest.fixture
def superuser(db):
    """Return a superuser for admin tests."""
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="notifications-admin",
        email="notifications-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser) -> Client:
    """Return an authenticated Django client for admin requests."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def notification_settings_row(db):
    """Return the synced read-only notification settings snapshot row."""
    return ensure_default_settings()


@pytest.fixture
def queued_message(db, notification_settings_row):
    """Return a queued notification message with two queued deliveries."""
    del notification_settings_row
    message = NotificationMessage.objects.create(
        template_key="quickscale_notifications.generic",
        subject="Queued message",
        from_email="QuickScale <noreply@example.com>",
        reply_to_email="support@example.com",
        rendered_text="Plain text body",
        rendered_html="<p>Plain text body</p>",
        context_json={"headline": "Queued message", "body": "Plain text body"},
        tags_json=["quickscale", "transactional"],
        metadata_json={"template": "notifications-generic"},
    )
    NotificationDelivery.objects.create(
        message=message,
        recipient_email="alpha@example.com",
    )
    NotificationDelivery.objects.create(
        message=message,
        recipient_email="beta@example.com",
    )
    return message


@pytest.fixture
def delivery_for_webhook(db, notification_settings_row):
    """Return a sent delivery row ready for webhook reconciliation tests."""
    del notification_settings_row
    message = NotificationMessage.objects.create(
        template_key="quickscale_notifications.generic",
        subject="Webhook message",
        from_email="QuickScale <noreply@example.com>",
        reply_to_email="support@example.com",
        rendered_text="Plain text body",
        rendered_html="<p>Plain text body</p>",
        context_json={"headline": "Webhook message", "body": "Plain text body"},
        status=NotificationMessage.Status.SENT,
        dispatched_at=timezone.now(),
        last_event_at=timezone.now(),
        tags_json=["quickscale", "transactional"],
        metadata_json={"template": "notifications-generic"},
    )
    return NotificationDelivery.objects.create(
        message=message,
        recipient_email="ops@example.com",
        provider_message_id="provider-msg-123",
        status=NotificationDelivery.Status.SENT,
        last_event_type="sent",
        dispatched_at=timezone.now(),
        last_event_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# bypass_rls marker registration and collection-time opt-in
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the bypass_rls marker and enable reuse-db by default."""
    shared_pytest_configure(config)
    # Enable reuse-db so the test database persists between
    # runs instead of being dropped and recreated.  Under a restricted
    # role (quickscale_test_role) a leftover test database may be
    # owned by postgres and cannot be dropped — with reuse_db enabled
    # no DROP DATABASE is attempted, avoiding the ownership/
    # duplicate-database failure on rerun.
    config.option.reuse_db = True
