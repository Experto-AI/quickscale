"""URL configuration for the QuickScale billing module."""

from django.urls import path

from quickscale_modules_billing.views import StripeWebhookView

app_name = "quickscale_billing"

urlpatterns = [
    path(
        "billing/webhooks/stripe/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]
