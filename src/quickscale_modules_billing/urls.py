"""URL configuration for the QuickScale billing module.

The module's mount (``billing/``) lives only in the manifest's
``url_includes`` wiring projection; every pattern here is module-relative and
every route name is snake_case without the module name (Module Conventions
rule 7).
"""

from django.urls import path

from quickscale_modules_billing.views import (
    BillingDashboardView,
    BillingPortalReturnView,
    CancelSubscriptionView,
    CreditBalanceView,
    CreditTransactionListView,
    CreateBillingPortalSessionView,
    CreateCheckoutSessionView,
    CreateSubscriptionCheckoutView,
    PlanListView,
    PricingPageView,
    PurchaseCancelView,
    PurchaseSuccessView,
    StripePublishableKeyView,
    StripeWebhookView,
    SubscriptionCancelView,
    SubscriptionDetailView,
    SubscriptionSuccessView,
)

DASHBOARD_PATH = "dashboard/"
PURCHASE_SUCCESS_PATH = "purchase/success/"
PURCHASE_CANCEL_PATH = "purchase/cancel/"
PORTAL_RETURN_PATH = "portal/return/"
PRICING_PATH = "pricing/"
SUBSCRIPTION_SUCCESS_PATH = "subscription/success/"
SUBSCRIPTION_CANCEL_PATH = "subscription/cancel/"

app_name = "quickscale_billing"

urlpatterns = [
    path(
        "api/config/",
        StripePublishableKeyView.as_view(),
        name="config",
    ),
    path(
        "api/plans/",
        PlanListView.as_view(),
        name="subscription_plans",
    ),
    path(
        "api/balance/",
        CreditBalanceView.as_view(),
        name="credit_balance",
    ),
    path(
        "api/transactions/",
        CreditTransactionListView.as_view(),
        name="credit_transactions",
    ),
    path(
        "api/purchase/checkout/",
        CreateCheckoutSessionView.as_view(),
        name="purchase_checkout",
    ),
    path(
        "api/subscription/",
        SubscriptionDetailView.as_view(),
        name="subscription_detail",
    ),
    path(
        "api/subscription/checkout/",
        CreateSubscriptionCheckoutView.as_view(),
        name="subscription_checkout",
    ),
    path(
        "api/subscription/cancel/",
        CancelSubscriptionView.as_view(),
        name="subscription_cancel_current",
    ),
    path(
        "api/portal/",
        CreateBillingPortalSessionView.as_view(),
        name="portal_session",
    ),
    path(
        DASHBOARD_PATH,
        BillingDashboardView.as_view(),
        name="dashboard",
    ),
    path(
        PORTAL_RETURN_PATH,
        BillingPortalReturnView.as_view(),
        name="portal_return",
    ),
    path(
        PRICING_PATH,
        PricingPageView.as_view(),
        name="pricing_page",
    ),
    path(
        PURCHASE_SUCCESS_PATH,
        PurchaseSuccessView.as_view(),
        name="purchase_success",
    ),
    path(
        PURCHASE_CANCEL_PATH,
        PurchaseCancelView.as_view(),
        name="purchase_cancel",
    ),
    path(
        SUBSCRIPTION_SUCCESS_PATH,
        SubscriptionSuccessView.as_view(),
        name="subscription_success",
    ),
    path(
        SUBSCRIPTION_CANCEL_PATH,
        SubscriptionCancelView.as_view(),
        name="subscription_cancel",
    ),
    path(
        "webhooks/stripe/",
        StripeWebhookView.as_view(),
        name="stripe_webhook",
    ),
]
