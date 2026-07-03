"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
)
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
    BillingError,
    BillingConfigurationError,
    BillingDisabledError,
    BillingSettingsSnapshot,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
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


def _enforce_csrf(request: HttpRequest) -> HttpResponse | None:
    middleware = CsrfViewMiddleware(lambda req: JsonResponse({"error": "Forbidden"}))
    return middleware.process_view(request, lambda req: JsonResponse({}), (), {})


def _parse_json_object_payload(
    request: HttpRequest,
) -> tuple[dict[str, Any] | None, HttpResponse | None]:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return None, JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"error": "JSON object payload expected"},
            status=400,
        )
    return payload, None


def _dashboard_url(*, organization: Any | None) -> str:
    return reverse("quickscale_billing:billing-dashboard")


def _pricing_url(*, organization: Any | None) -> str:
    return reverse("quickscale_billing:pricing-page")


_ORG_SELECTION_REQUIRED_ERROR = "Organization selection required."

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


class PlanListView(APIView):
    """Return the public recurring billing catalog."""

    permission_classes = [AllowAny]
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


@method_decorator(csrf_exempt, name="dispatch")
class CreateCheckoutSessionView(View):
    """Create a hosted Stripe checkout session for a one-time credit purchase."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request,
            require_owner=True,
        )
        if organization is None:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )
        if access_denied:
            return HttpResponse(status=403)

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateCheckoutSessionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        try:
            checkout_url = create_checkout_session(
                request.user,
                serializer.validated_data["plan"],
                reverse("quickscale_billing:purchase-success"),
                reverse("quickscale_billing:purchase-cancel"),
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse({"checkout_url": checkout_url})


@method_decorator(csrf_exempt, name="dispatch")
class CreateSubscriptionCheckoutView(View):
    """Create a hosted Stripe checkout session for a recurring subscription."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request,
            require_owner=True,
        )
        if organization is None:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )
        if access_denied:
            return HttpResponse(status=403)

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateSubscriptionCheckoutSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        try:
            checkout_url = create_subscription_checkout_session(
                request.user,
                serializer.validated_data["plan"],
                reverse("quickscale_billing:subscription-success"),
                reverse("quickscale_billing:subscription-cancel"),
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse({"checkout_url": checkout_url})


@method_decorator(csrf_exempt, name="dispatch")
class CancelSubscriptionView(View):
    """Cancel the authenticated organization's current recurring subscription."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request,
            require_owner=True,
        )
        if organization is None:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )
        if access_denied:
            return HttpResponse(status=403)

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CancelSubscriptionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        try:
            cancel_current_subscription(
                request.user,
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return HttpResponse(status=204)


@method_decorator(csrf_exempt, name="dispatch")
class CreateBillingPortalSessionView(View):
    """Create a hosted Stripe billing portal session for the current organization."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request,
            require_owner=True,
        )
        if organization is None:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )
        if access_denied:
            return HttpResponse(status=403)

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateBillingPortalSessionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        try:
            portal_url = create_billing_portal_session(
                request.user,
                reverse("quickscale_billing:portal-return"),
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse({"portal_url": portal_url})


class CreditBalanceView(APIView):
    """Return the authenticated organization's current credit balance snapshot."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request._request,
            require_owner=True,
        )
        if organization is None:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)
        if access_denied:
            return Response(status=403)

        balance, _ = CreditBalance.all_objects.get_or_create(
            organization=organization,
            defaults={"balance": 0},
        )
        serializer = CreditBalanceSerializer(balance)
        return Response(serializer.data)


class CreditTransactionListView(APIView):
    """Return the authenticated organization's paginated credit transaction history."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]
    pagination_class = _TransactionPagination

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request._request,
            require_owner=True,
        )
        if organization is None:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)
        if access_denied:
            return Response(status=403)

        queryset = CreditTransaction.all_objects.filter(organization=organization)
        queryset = queryset.order_by("-created_at", "-id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CreditTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SubscriptionDetailView(APIView):
    """Return the authenticated organization's current recurring subscription."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization, access_denied = _resolve_request_organization(
            request._request,
            require_owner=True,
        )
        if organization is None:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)
        if access_denied:
            return Response(status=403)

        subscription = (
            Subscription.all_objects.select_related("plan")
            .filter(organization=organization)
            .filter(Subscription.current_status_q())
            .order_by("-id")
            .first()
        )
        if subscription is None:
            return Response({"error": "Current subscription not found."}, status=404)

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class StripePublishableKeyView(APIView):
    """Return the authenticated Stripe publishable key for billing UI clients."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization = getattr(request._request, "org", None)
        if organization is None:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)

        snapshot = BillingSettingsSnapshot.from_settings()
        try:
            return Response({"publishable_key": snapshot.resolve_publishable_key()})
        except BillingConfigurationError as exc:
            return Response({"error": str(exc)}, status=500)
        except BillingError as exc:
            return Response({"error": str(exc)}, status=500)


class BillingDashboardView(LoginRequiredMixin, TemplateView):
    """Module-owned billing dashboard mount page."""

    template_name = "quickscale_modules_billing/dashboard.html"

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
            return redirect("quickscale_billing:pricing-page")
        if access_denied:
            return HttpResponse(status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        organization = getattr(self.request, "org", None)
        if organization is None:
            return context

        balance, _ = CreditBalance.all_objects.get_or_create(
            organization=organization,
            defaults={"balance": 0},
        )
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

    template_name = "quickscale_modules_billing/pricing.html"

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

    template_name = "quickscale_modules_billing/billing/portal_return.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseSuccessView(TemplateView):
    """Public success landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class PurchaseCancelView(TemplateView):
    """Public cancel landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionSuccessView(TemplateView):
    """Public success landing page for recurring checkout returns."""

    template_name = "quickscale_modules_billing/subscription_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url(
            organization=getattr(self.request, "org", None),
        )
        return context


class SubscriptionCancelView(TemplateView):
    """Public cancel landing page for recurring checkout returns."""

    template_name = "quickscale_modules_billing/subscription_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url(
            organization=getattr(self.request, "org", None),
        )
        return context


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """Transport-only Stripe webhook endpoint for billing."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        try:
            result = handle_stripe_event(
                body=request.body,
                signature=request.headers.get("Stripe-Signature", ""),
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingWebhookSignatureError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingWebhookError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "status": "accepted",
                "duplicate": result.duplicate,
                "event_type": result.event_type,
                "processing_status": result.status,
            }
        )
