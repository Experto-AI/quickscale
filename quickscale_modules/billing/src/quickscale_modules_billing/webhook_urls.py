"""Webhook-only URLconf for the QuickScale billing module.

Rule 1 (D3): a switched-off billing module unmounts its public pages and
APIs, but the Stripe webhook stays mounted so a provider retry still gets the
module's clean 404 refusal (rule 26) instead of an unrouted Django 404.
"""

from django.urls import path

from quickscale_modules_billing.views import StripeWebhookView

app_name = "quickscale_billing"

urlpatterns = [
    path(
        "webhooks/stripe/",
        StripeWebhookView.as_view(),
        name="stripe_webhook",
    ),
]
