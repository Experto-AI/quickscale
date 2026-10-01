"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
)
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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


def _resolve_request_organization(
    request: HttpRequest,
    *,
    require_owner: bool = False,
) -> tuple[Any | None, bool]:
    organization = getattr(request, "org", None)
    if organization is None:
        return None, False

    if require_owner:
        from quickscale_modules_orgs.models import OrgRole
        from quickscale_modules_orgs.permissions import user_has_org_role

        if not user_has_org_role(request.user, organization, OrgRole.OWNER):
            return organization, True

    return organization, False


def _require_authenticated(request: Request) -> None:
    """Raise the module's 401 for a caller without a session."""
    if not request.user.is_authenticated:
        raise NotAuthenticated("Authentication required")


def _require_request_organization(
    request: Request,
    *,
    require_owner: bool = True,
) -> Any:
    """Return the request's organization, refusing a missing or unauthorized one."""
    organization, access_denied = _resolve_request_organization(
        request._request,
        require_owner=require_owner,
    )
    if organization is None:
        raise OrgSelectionRequiredError()
    if access_denied:
        raise PermissionDenied("Forbidden")
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


class _TransactionPagination(PageNumberPagination):
    """Paginate transactions without wrapping the response payload."""

    page_size = 25
    page_size_query_param = None

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(data)


class BillingSessionAuthentication(SessionAuthentication):
    """Session authentication that keeps a 401 challenge for anonymous callers.

    DRF answers an unauthenticated request 403 when the authentication scheme
    declares no challenge header; the billing API has always answered 401, so
    the scheme names its challenge.
    """

    def authenticate_header(self, request: Request) -> str:
        del request
        return "Session"


class _BillingAPIView(APIView):
    """Shared DRF wiring for billing's JSON endpoints.

    Session authentication only (DRF enforces CSRF on unsafe methods),
    ``AllowAny`` because each view performs its own authentication and
    organization checks, and JSON-only parsing and rendering so an
    HTML-preferring client never receives DRF's browsable-API page instead
    of the one QuickScale error shape (Module Conventions rule 9).
    """

    authentication_classes = [BillingSessionAuthentication]
    permission_classes = [AllowAny]
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

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del request, args, kwargs
        queryset = Plan.objects.filter(
            is_active=True,
            billing_interval__in=[
                Plan.BillingInterval.MONTHLY,
                Plan.BillingInterval.YEARLY,
            ],
        ).order_by("name", "pk")
        serializer = PlanSerializer(queryset, many=True)
        return Response(serializer.data)


class CreateCheckoutSessionView(_RenderedAPIView):
    """Create a hosted Stripe checkout session for a one-time credit purchase."""

    http_method_names = ["post"]
    # Tighter than the generated user/anon defaults; the rate for this scope
    # is contributed by the billing wiring spec.
    throttle_scope = "quickscale_billing_checkout"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        _require_authenticated(request)
        organization = _require_request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateCheckoutSessionSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        checkout_url = create_checkout_session(
            request.user,
            plan=serializer.validated_data["plan"],
            success_url=reverse("quickscale_billing:purchase_success"),
            cancel_url=reverse("quickscale_billing:purchase_cancel"),
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
        _require_authenticated(request)
        organization = _require_request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateSubscriptionCheckoutSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        checkout_url = create_subscription_checkout_session(
            request.user,
            plan=serializer.validated_data["plan"],
            success_url=reverse("quickscale_billing:subscription_success"),
            cancel_url=reverse("quickscale_billing:subscription_cancel"),
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
        _require_authenticated(request)
        organization = _require_request_organization(request)

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
        _require_authenticated(request)
        organization = _require_request_organization(request)

        payload = _json_object_payload(request)
        serializer = CreateBillingPortalSessionSerializer(data=payload)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        portal_url = create_billing_portal_session(
            request.user,
            return_url=reverse("quickscale_billing:portal_return"),
            organization=organization,
        )
        return Response({"portal_url": portal_url})


class CreditBalanceView(_BillingAPIView):
    """Return the authenticated organization's current credit balance snapshot."""

    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        _require_authenticated(request)
        organization = _require_request_organization(request)

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
        _require_authenticated(request)
        organization = _require_request_organization(request)

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
        _require_authenticated(request)
        organization = _require_request_organization(request)

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
        _require_authenticated(request)

        organization = getattr(request._request, "org", None)
        if organization is None:
            raise OrgSelectionRequiredError()

        snapshot = BillingSettingsSnapshot.from_settings()
        return Response({"publishable_key": snapshot.resolve_publishable_key()})


class BillingDashboardView(LoginRequiredMixin, TemplateView):
    """Module-owned billing dashboard mount page."""

    template_name = "quickscale_billing/dashboard.html"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        organization, access_denied = _resolve_request_organization(
            request,
            require_owner=True,
        )
        if organization is None:
            return redirect("quickscale_billing:pricing_page")
        if access_denied:
            return HttpResponse(status=403)
        return super().dispatch(request, *args, **kwargs)

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


class PricingPageView(TemplateView):
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


class BillingPortalReturnView(TemplateView):
    """Public return page for hosted Stripe billing portal sessions."""

    template_name = "quickscale_billing/billing/portal_return.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseSuccessView(TemplateView):
    """Public success landing page for hosted checkout returns."""

    template_name = "quickscale_billing/purchase_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseCancelView(TemplateView):
    """Public cancel landing page for hosted checkout returns."""

    template_name = "quickscale_billing/purchase_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionSuccessView(TemplateView):
    """Public success landing page for recurring checkout returns."""

    template_name = "quickscale_billing/subscription_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionCancelView(TemplateView):
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
