"""URL configuration for the QuickScale notifications module.

The module's mount lives in its manifest's ``url_includes`` entry
(``notifications/``); this URLconf holds no prefix (Module Conventions rule 7).
"""

from django.urls import path

from quickscale_modules_notifications.views import NotificationWebhookView

app_name = "quickscale_notifications"

urlpatterns = [
    path(
        "webhooks/resend/",
        NotificationWebhookView.as_view(),
        name="resend_webhook",
    ),
]
