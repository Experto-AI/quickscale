"""URL configuration for the QuickScale billing module."""

from django.urls import path

from quickscale_modules_billing.views import (
    CreditBalanceView,
    CreditTransactionListView,
    CreateCheckoutSessionView,
    CreateSubscriptionCheckoutView,
    PlanListView,
    PurchaseCancelView,
    PurchaseSuccessView,
    StripeWebhookView,
    SubscriptionCancelView,
    SubscriptionDetailView,
    SubscriptionSuccessView,
)

PURCHASE_SUCCESS_PATH = "billing/purchase/success/"
PURCHASE_CANCEL_PATH = "billing/purchase/cancel/"
SUBSCRIPTION_SUCCESS_PATH = "billing/subscription/success/"
SUBSCRIPTION_CANCEL_PATH = "billing/subscription/cancel/"

app_name = "quickscale_billing"

urlpatterns = [
    path(
        "api/billing/plans/",
        PlanListView.as_view(),
        name="subscription-plans",
    ),
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
        "api/billing/subscription/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
    path(
        "api/billing/subscription/checkout/",
        CreateSubscriptionCheckoutView.as_view(),
        name="subscription-checkout",
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
        SUBSCRIPTION_SUCCESS_PATH,
        SubscriptionSuccessView.as_view(),
        name="subscription-success",
    ),
    path(
        SUBSCRIPTION_CANCEL_PATH,
        SubscriptionCancelView.as_view(),
        name="subscription-cancel",
    ),
    path(
        "billing/webhooks/stripe/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]
