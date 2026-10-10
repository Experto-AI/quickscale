"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.exceptions import (
    NotFound,
    ValidationError,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_core.runtime import (
    PlainListPagination,
    QuickscaleSessionAuthentication,
)
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingWebhookError,
    OrgSelectionRequiredError,
)
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_billing.serializers import (
    CancelSubscriptionSerializer,
    CreateCheckoutSessionSerializer,
    CreateBillingPortalSessionSerializer,
    CreateSubscriptionCheckoutSerializer,
    CreditBalanceSerializer,
    CreditTransactionSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)
from quickscale_modules_billing.services import (
    BillingSettingsSnapshot,
    cancel_current_subscription,
    create_checkout_session,
    create_billing_portal_session,
    create_subscription_checkout_session,
    handle_stripe_event,
)
from quickscale_modules_orgs.models import OrgRole
from quickscale_modules_orgs.permissions import (
    HasOrgRole,
    OrgRoleMixin,
    resolve_request_org,
)


def _request_organization(request: Request) -> Any:
    """Return the request's organization, refusing a caller without one.

    The view's ``IsAuthenticated``/``HasOrgRole`` guard has authorized the
    caller (Module Conventions rule 19), so this only resolves the
    organization the handler attributes its work to.  A superuser passes
    ``HasOrgRole`` without organization context, so the missing-selection
    case still answers the module's ``org_selection_required`` error.
    Billing's routes are flat, so there is no ``org_slug`` route kwarg; the
    organization comes from the middleware-populated ``request.org``.
    """
    organization = resolve_request_org(request._request, {})
    if organization is None:
        raise OrgSelectionRequiredError()
    return organization


def _json_object_payload(request: Request) -> Mapping[str, Any]:
    """Return the request's JSON object payload or fail validation."""
    payload = request.data
    if not isinstance(payload, Mapping):
        raise ValidationError({"non_field_errors": ["JSON object payload expected"]})
    return payload


def _dashboard_url(*, organization: Any | None) -> str:
    return reverse("quickscale_billing:dashboard")


def _pricing_url(*, organization: Any | None) -> str:
    return reverse("quickscale_billing:pricing_page")


_ZERO_DECIMAL_PRICE_CURRENCIES = frozenset({"jpy"})


def _format_price_cents(cents: int, currency: str) -> str:
    normalized_currency = (currency or "usd").strip().lower() or "usd"
    decimal_places = 0 if normalized_currency in _ZERO_DECIMAL_PRICE_CURRENCIES else 2
    amount = Decimal(cents) / (Decimal(10) ** decimal_places)
    amount_format = ",.0f" if decimal_places == 0 else ",.2f"
    formatted_amount = format(amount, amount_format)
    if normalized_currency == "usd":
        return f"${formatted_amount}"
    return f"{normalized_currency.upper()} {formatted_amount}"


class _TransactionPagination(PlainListPagination):
    """Transactions page size driven by QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE."""

    page_size_setting = "QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE"


class _PlanPagination(PlainListPagination):
    """Plan catalog page size driven by QUICKSCALE_BILLING_PLANS_PER_PAGE."""

    page_size_setting = "QUICKSCALE_BILLING_PLANS_PER_PAGE"


class _BillingAPIView(APIView):
    """Shared DRF wiring for billing's JSON endpoints.

    Session authentication only, through core's one session authentication
    class (DRF enforces CSRF on unsafe methods), and billing data is
    owner-only: the default guard is ``IsAuthenticated`` plus orgs'
    ``HasOrgRole(OrgRole.OWNER)``, and a public endpoint states its
    ``[AllowAny]`` guard on the view (Module Conventions rule 19).
    JSON-only parsing and rendering so an HTML-preferring client never
    receives DRF's browsable-API page instead of the one QuickScale error
    shape (Module Conventions rule 9).
    """

    authentication_classes = [QuickscaleSessionAuthentication]
    permission_classes = [IsAuthenticated, HasOrgRole(OrgRole.OWNER)]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]

    def handle_exception(self, exc: Exception) -> Response:
        """Classify a webhook-scoped provider failure as a server error here.

        ``BillingWebhookError`` carries 400 for the signature-verified webhook
        transport (Module Conventions rule 26); on a customer-facing endpoint
        the same provider anomaly is a server-side failure, so it answers the
        base error's 500 instead.
        """
        if isinstance(exc, BillingWebhookError):
            exc = BillingError(str(exc))
        return super().handle_exception(exc)


class _RenderedAPIView(_BillingAPIView):
    """APIView variant that renders the response during dispatch.

    DRF 3.16+ defers response rendering to the WSGI handler layer, so
    calling ``as_view()(request)`` directly (outside the middleware
    stack) leaves ``response.content`` inaccessible.  This mixin renders
    the response at the end of ``dispatch()`` so that the content is
    available immediately — preserving the pre-existing behavior for
    direct view invocations.
    """

    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponse:
        response = super().dispatch(*args, **kwargs)
        if isinstance(response, Response):
            response.render()
        return response


class PlanListView(_BillingAPIView):
    """Return the public recurring billing catalog."""

    http_method_names = ["get"]
    # The catalog is the module's one public JSON endpoint, so it states its
    # own AllowAny guard instead of the base's owner-only default (rule 19).
    permission_classes = [AllowAny]
    pagination_class = _PlanPagination

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        queryset = Plan.objects.filter(
            is_active=True,
            billing_interval__in=[
                Plan.BillingInterval.MONTHLY,
                Plan.BillingInterval.YEARLY,
            ],
        ).order_by("name", "pk")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = PlanSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CreateCheckoutSessionView(_RenderedAPIView):
    """Create a hosted Stripe checkout session for a one-time credit purchase."""

    http_method_names = ["post"]
    # Tighter than the generated user/anon defaults; the rate for this scope
    # is contributed by the billing wiring spec.
    throttle_scope = "quickscale_billing_checkout"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateCheckoutSessionSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        checkout_url = create_checkout_session(
            request.user,
            plan=serializer.validated_data["plan"],
            success_url=request.build_absolute_uri(
                reverse("quickscale_billing:purchase_success")
            ),
            cancel_url=request.build_absolute_uri(
                reverse("quickscale_billing:purchase_cancel")
            ),
            organization=organization,
        )
        return Response({"checkout_url": checkout_url})


class CreateSubscriptionCheckoutView(_RenderedAPIView):
    """Create a hosted Stripe checkout session for a recurring subscription."""

    http_method_names = ["post"]
    # Tighter than the generated user/anon defaults; the rate for this scope
    # is contributed by the billing wiring spec.
    throttle_scope = "quickscale_billing_checkout"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateSubscriptionCheckoutSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        checkout_url = create_subscription_checkout_session(
            request.user,
            plan=serializer.validated_data["plan"],
            success_url=request.build_absolute_uri(
                reverse("quickscale_billing:subscription_success")
            ),
            cancel_url=request.build_absolute_uri(
                reverse("quickscale_billing:subscription_cancel")
            ),
            organization=organization,
        )
        return Response({"checkout_url": checkout_url})


class CancelSubscriptionView(_RenderedAPIView):
    """Cancel the authenticated organization's current recurring subscription."""

    http_method_names = ["post"]
    # Stripe-calling session endpoint; the rate for this scope is contributed
    # by the billing wiring spec.
    throttle_scope = "quickscale_billing_portal"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        payload = _json_object_payload(request)
        serializer = CancelSubscriptionSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        cancel_current_subscription(
            request.user,
            organization=organization,
        )
        return Response(status=204)


class CreateBillingPortalSessionView(_RenderedAPIView):
    """Create a hosted Stripe billing portal session for the current organization."""

    http_method_names = ["post"]
    # Stripe-calling session endpoint; the rate for this scope is contributed
    # by the billing wiring spec.
    throttle_scope = "quickscale_billing_portal"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateBillingPortalSessionSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        portal_url = create_billing_portal_session(
            request.user,
            return_url=request.build_absolute_uri(
                reverse("quickscale_billing:portal_return")
            ),
            organization=organization,
        )
        return Response({"portal_url": portal_url})


class CreditBalanceView(_BillingAPIView):
    """Return the authenticated organization's current credit balance snapshot."""

    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        balance = CreditBalance.all_objects.filter(organization=organization).first()
        if balance is None:
            balance = CreditBalance(organization=organization, balance=0)
        serializer = CreditBalanceSerializer(balance)
        return Response(serializer.data)


class CreditTransactionListView(_BillingAPIView):
    """Return the authenticated organization's paginated credit transaction history."""

    http_method_names = ["get"]
    pagination_class = _TransactionPagination

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        queryset = CreditTransaction.all_objects.filter(organization=organization)
        queryset = queryset.order_by("-created_at", "-id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CreditTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SubscriptionDetailView(_BillingAPIView):
    """Return the authenticated organization's current recurring subscription."""

    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        organization = _request_organization(request)

        subscription = (
            Subscription.all_objects.select_related("plan")
            .filter(organization=organization)
            .filter(Subscription.current_status_q())
            .order_by("-id")
            .first()
        )
        if subscription is None:
            raise NotFound("Current subscription not found.")

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class StripePublishableKeyView(_BillingAPIView):
    """Return the authenticated Stripe publishable key for billing UI clients."""

    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        _request_organization(request)

        snapshot = BillingSettingsSnapshot.from_settings()
        return Response({"publishable_key": snapshot.resolve_publishable_key()})


class BillingDashboardView(LoginRequiredMixin, OrgRoleMixin, TemplateView):
    """Module-owned billing dashboard mount page.

    Login is the page gate; the dashboard is owner-only, so ``OrgRoleMixin``
    enforces the active organization's ``owner`` role (Module Conventions
    rule 19).
    """

    template_name = "quickscale_billing/dashboard.html"
    min_org_role = OrgRole.OWNER

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Require login first, then the owner org role."""
        return cast(HttpResponse, super().dispatch(request, *args, **kwargs))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        organization = getattr(self.request, "org", None)
        if organization is None:
            return context

        balance = CreditBalance.all_objects.filter(organization=organization).first()
        if balance is None:
            balance = CreditBalance(organization=organization, balance=0)
        recent_transactions = list(
            CreditTransaction.all_objects.filter(organization=organization).order_by(
                "-created_at",
                "-id",
            )[:10]
        )
        subscription = (
            Subscription.all_objects.select_related("plan")
            .filter(organization=organization)
            .filter(Subscription.current_status_q())
            .order_by("-id")
            .first()
        )
        context.update(
            {
                "balance": balance,
                "pricing_url": _pricing_url(organization=organization),
                "recent_transactions": recent_transactions,
                "subscription": subscription,
            }
        )
        return context


class BillingPublicReadMixin:
    """Explicit public-read declaration for billing's unauthenticated pages.

    The pricing page and the Stripe return pages are public by design; the
    named mixin states that guard decision on each view (Module Conventions
    rule 19), so no page carries an unstated or hand-written guard.
    """


class PricingPageView(BillingPublicReadMixin, TemplateView):
    """Public billing pricing mount page."""

    template_name = "quickscale_billing/pricing.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        plans = list(
            Plan.objects.filter(is_active=True).order_by(
                "billing_interval",
                "price_cents",
                "pk",
            )
        )
        for plan in plans:
            plan.price_display = _format_price_cents(plan.price_cents, plan.currency)

        pricing_url = _pricing_url(organization=None)
        context.update(
            {
                "plans": plans,
                "billing_url": (
                    _dashboard_url(organization=None)
                    if self.request.user.is_authenticated
                    else pricing_url
                ),
                "billing_destination_kind": "dashboard",
                "pricing_login_url": (
                    f"{resolve_url(settings.LOGIN_URL)}?next={pricing_url}"
                ),
                "viewer_is_authenticated": self.request.user.is_authenticated,
            }
        )
        return context


class BillingPortalReturnView(BillingPublicReadMixin, TemplateView):
    """Public return page for hosted Stripe billing portal sessions."""

    template_name = "quickscale_billing/portal_return.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseSuccessView(BillingPublicReadMixin, TemplateView):
    """Public success landing page for hosted checkout returns."""

    template_name = "quickscale_billing/purchase_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseCancelView(BillingPublicReadMixin, TemplateView):
    """Public cancel landing page for hosted checkout returns."""

    template_name = "quickscale_billing/purchase_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionSuccessView(BillingPublicReadMixin, TemplateView):
    """Public success landing page for recurring checkout returns."""

    template_name = "quickscale_billing/subscription_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionCancelView(BillingPublicReadMixin, TemplateView):
    """Public cancel landing page for recurring checkout returns."""

    template_name = "quickscale_billing/subscription_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class StripeWebhookView(APIView):
    """Transport-only Stripe webhook endpoint for billing.

    The signature header is the authentication (Module Conventions rule 26),
    so the view declares no authentication, permission, or throttle classes
    and passes the raw body and signature to one ``services.py`` function.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []
    http_method_names = ["post"]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        result = handle_stripe_event(
            body=request.body,
            signature=request.headers.get("Stripe-Signature", ""),
        )
        return Response({"status": "accepted", "duplicate": result.duplicate})
