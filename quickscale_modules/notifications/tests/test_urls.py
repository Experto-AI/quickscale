"""Tests for notifications module URLs."""

from django.urls import resolve, reverse

from quickscale_modules_notifications.views import NotificationWebhookView


def test_resend_webhook_url_resolves() -> None:
    url = reverse("quickscale_notifications:resend-webhook")
    match = resolve(url)

    assert url == "/notifications/webhooks/resend/"
    assert match.func.view_class is NotificationWebhookView
