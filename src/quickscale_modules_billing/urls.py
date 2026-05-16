"""URL configuration for the QuickScale billing module."""

from django.urls import path

from quickscale_modules_billing.views import (
    CreditBalanceView,
    CreditTransactionListView,
    CreateCheckoutSessionView,
    PurchaseCancelView,
    PurchaseSuccessView,
    StripeWebhookView,
)

PURCHASE_SUCCESS_PATH = "billing/purchase/success/"
PURCHASE_CANCEL_PATH = "billing/purchase/cancel/"

app_name = "quickscale_billing"

urlpatterns = [
    path(
        "api/billing/balance/",
        CreditBalanceView.as_view(),
        name="credit-balance",
    ),
    path(
        "api/billing/transactions/",
        CreditTransactionListView.as_view(),
        name="credit-transactions",
    ),
    path(
        "api/billing/purchase/checkout/",
        CreateCheckoutSessionView.as_view(),
        name="purchase-checkout",
    ),
    path(
        PURCHASE_SUCCESS_PATH,
        PurchaseSuccessView.as_view(),
        name="purchase-success",
    ),
    path(
        PURCHASE_CANCEL_PATH,
        PurchaseCancelView.as_view(),
        name="purchase-cancel",
    ),
    path(
        "billing/webhooks/stripe/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]
