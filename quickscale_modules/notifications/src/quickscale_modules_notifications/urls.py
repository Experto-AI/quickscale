"""URL configuration for the QuickScale notifications module."""

from django.urls import path

from quickscale_modules_notifications.views import NotificationWebhookView

app_name = "quickscale_notifications"

urlpatterns = [
    path(
        "notifications/webhooks/resend/",
        NotificationWebhookView.as_view(),
        name="resend-webhook",
    ),
]
